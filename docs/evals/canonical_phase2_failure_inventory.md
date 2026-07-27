# Canonical Phase 2 — pytest failure inventory (derived)

**Generated:** 2026-07-25 18:04 UTC
**Purpose:** Transparent derived inventory correcting Item 15 historical evidence limitation (explicit decision 2026-07-25).

## Historical evidence limitation (disclosed)

Item 15 originally claimed `docs/evals/canonical_phase2_failure_inventory.md` existed with 100 verified rows. **That file was never committed to git.** The only surviving authoritative enumeration is `/tmp/pytest-failures-item15.txt`, captured during the Item 15 measurement run at commit `2fce033`.

This document is a **derived reconstruction** from that enumeration plus commit-range forensics. It does **not** claim all 112 original failure identities were individually recovered or classified.

### Reconciliation to rev-10 scope (112 failures at `8792338`)

| Population | Count | Status |
|------------|------:|--------|
| **A** — Captured Item 15 failures (enumerated at `2fce033`) | 100 | Individually classified A–G below |
| **B** — Stale sentinel identity | 1 | Recorded; outside A–G totals |
| **C** — Historical identities not preserved | 11 | Group-level attribution only; no per-identity categories |
| **Total** | **112** | Matches rev-10 scope at `8792338` |

- Original measurement (`8792338`): 4177 passed / 112 failed / 2 skipped / 6 xfailed
- Item 15 capture (`2fce033`): 4256 passed / 100 failed / 2 skipped / 6 xfailed
- Delta before capture: 12 identities dropped (1 stale sentinel + 11 production-side resolutions)

## Current acceptance evidence (HEAD `dcd5a3e`)

| Gate | Result |
|------|--------|
| Full pytest | **4358 passed, 2 skipped, 6 xfailed, 0 failed** |
| Production parity | **120 exact_match / 0 approved_difference / 0 critical_mismatch** (`runtime_a=imperative_canonical`, `runtime_b=resource_planner_graph`, `base_105_loaded=105`) |
| Focused architecture guards | **41 passed** (`test_dual_runtime_lane_parity`, `test_canonical_planning_architecture`, `test_dual_runtime_single_orchestration`, `test_production_parity_evaluator`) |
| Protected eval/fixture paths | Clean at HEAD (no committed artifact drift) |

All Population A rows were resolved by Item 17 and are green at HEAD.

---

## Population A — Captured Item 15 failures (100)

**Source:** `/tmp/pytest-failures-item15.txt` (exact identities, sorted)
**Measured at:** commit `2fce033` — 4256 passed / 100 failed / 2 skipped / 6 xfailed

### Category specification (Item 15)

| Cat | Meaning |
|-----|---------|
| **A** | Tests assuming canonical planning can be disabled |
| **B** | Tests expecting legacy `query_to_intent` or `evidence_planning` |
| **C** | Tests expecting live `/chat` to attach `ResourcePlan` through old planner |
| **D** | Tests expecting legacy dispatch fallback |
| **E** | Clarification `EvidencePlan` contract failures |
| **F** | Configuration tests referencing removed flags |
| **G** | Genuine regressions unrelated to test assumptions |

### Category totals (Population A only)

| Category | Count |
|----------|------:|
| **A** | 12 |
| **B** | 25 |
| **C** | 2 |
| **D** | 21 |
| **E** | 1 |
| **F** | 14 |
| **G** | 25 |
| **Total** | **100** |

**Note on Category G:** Production dual-runtime parity Category G (the seven HIL/SPL divergences) was cleared by Item 32 (`48a217d`). The 25 Population-A **G** rows are unit/integration drift under canonical-only runtime — not production parity Category G.

**Reclassification check:** Derived totals match the interim plan record (A=12, B=25, C=2, D=21, E=1, F=14, G=25). No aggregate adjustment was required.

### Inventory table

| # | Test file | Test name | Cat | Old assumption / defect | Canonical expectation | Resolving fix / evidence |
|--:|-----------|-----------|-----|-------------------------|----------------------|--------------------------|
| 1 | `app/tests/test_105_path_honoring.py` | `test_exact_105_smb_top_hosts_sets_needs_spl_true` | **G** | 105-map needs_spl hint from catalogue binding | Canonical known-lane preserves needs_spl from template registry | Code fix: catalogue bind → evidence_plan.needs_spl (item 17); green at `dcd5a3e` |
| 2 | `app/tests/test_batch5_session_context.py` | `test_follow_up_spl_refine_revalidates_previous_spl` | **G** | Session SPL refine revalidates prior candidate | Both runtimes seed session_context_resolution; refine path unchanged | Code fix: session refine dispatch branch (item 17); green at `dcd5a3e` |
| 3 | `app/tests/test_canonical_telemetry_correlation.py` | `test_persist_failure_does_not_populate_fixture_store` | **G** | Telemetry persist failure isolation | Canonical telemetry must not leak fixture store on failure | Code fix: persist_failure guard (item 17); green at `dcd5a3e` |
| 4 | `app/tests/test_catalogue_bind_surface_agreement.py` | `test_catalogue_bind_surface_agreement` | **G** | Catalogue bind surface agreement across layers | Canonical routing must keep bind surface aligned | Code fix: bind surface reconciliation (item 17); green at `dcd5a3e` |
| 5 | `app/tests/test_chat_control_plane_golden.py` | `test_mitre_mapping_without_alert_context_requires_clarification` | **G** | MITRE-without-context returns clarification HIL | Canonical session/MITRE clarify path via context_finalize | Code fix: MITRE clarify under canonical path (item 17); green at `dcd5a3e` |
| 6 | `app/tests/test_chat_progress_stream.py` | `test_resource_planner_invoke_forwards_pipeline_progress` | **G** | RP graph forwards progress events | run_resource_planner_graph must emit same stages as imperative | Code fix: progress through canonical bootstrap (item 17); green at `dcd5a3e` |
| 7 | `app/tests/test_cov_q046_observation_window_stage3l_s3_step7.py` | `test_cov_q046_observation_window_closes_with_zero_unexpected` | **A** | Lab authority / observation window assumes optional canonical cutover | Canonical planning always on; lab authority applies under canonical dispatch | Rewrite test setup for canonical-only (item 17); green at `dcd5a3e` |
| 8 | `app/tests/test_cov_q046_observation_window_stage3l_s3_step7.py` | `test_in_pattern_lab_authority_applies_with_slots` | **A** | Lab authority / observation window assumes optional canonical cutover | Canonical planning always on; lab authority applies under canonical dispatch | Rewrite test setup for canonical-only (item 17); green at `dcd5a3e` |
| 9 | `app/tests/test_curated_enrichment_activation_phase4.py` | `test_flag_off_preserves_current_chat_behavior` | **F** | Curated enrichment activation can be disabled via flag | Canonical planning is always authoritative; flag-off byte-identity is not a runtime mode | Test rewrite for canonical-on behaviour (item 17); green at `dcd5a3e` |
| 10 | `app/tests/test_evidence_loop_all_tier_discovery.py` | `test_live_data_spl_query_runs_real_discovery_hops_in_mock_mode` | **G** | All-tier discovery loop in mock mode | Discovery loop after canonical planned outcome only | Code fix: gate discovery on planned status (item 17); green at `dcd5a3e` |
| 11 | `app/tests/test_evidence_loop_graph.py` | `test_cp_on_chronology_is_deterministic_without_advisory_flag` | **B** | LangGraph evidence loop hub via graph_node_evidence_planning on CP-on path | Initial planning via run_canonical_planning; loop re-entry only after loop_initialized | Rewire graph tests to canonical entry + loop re-entry seam (item 17); green at `dcd5a3e` |
| 12 | `app/tests/test_evidence_loop_graph.py` | `test_cp_on_loop_state_is_bounded` | **B** | LangGraph evidence loop hub via graph_node_evidence_planning on CP-on path | Initial planning via run_canonical_planning; loop re-entry only after loop_initialized | Rewire graph tests to canonical entry + loop re-entry seam (item 17); green at `dcd5a3e` |
| 13 | `app/tests/test_evidence_loop_graph.py` | `test_cp_on_merges_loop_hops_into_source_evidence` | **B** | LangGraph evidence loop hub via graph_node_evidence_planning on CP-on path | Initial planning via run_canonical_planning; loop re-entry only after loop_initialized | Rewire graph tests to canonical entry + loop re-entry seam (item 17); green at `dcd5a3e` |
| 14 | `app/tests/test_evidence_loop_graph.py` | `test_cp_on_recipe_driven_turn_runs_through_real_langgraph_path` | **B** | LangGraph evidence loop hub via graph_node_evidence_planning on CP-on path | Initial planning via run_canonical_planning; loop re-entry only after loop_initialized | Rewire graph tests to canonical entry + loop re-entry seam (item 17); green at `dcd5a3e` |
| 15 | `app/tests/test_evidence_loop_graph.py` | `test_cp_on_run_terminates_and_surfaces_loop_trace` | **B** | LangGraph evidence loop hub via graph_node_evidence_planning on CP-on path | Initial planning via run_canonical_planning; loop re-entry only after loop_initialized | Rewire graph tests to canonical entry + loop re-entry seam (item 17); green at `dcd5a3e` |
| 16 | `app/tests/test_evidence_loop_graph.py` | `test_debug_trace_surfaces_mcp_calls_for_recipe_driven_turn` | **B** | LangGraph evidence loop hub via graph_node_evidence_planning on CP-on path | Initial planning via run_canonical_planning; loop re-entry only after loop_initialized | Rewire graph tests to canonical entry + loop re-entry seam (item 17); green at `dcd5a3e` |
| 17 | `app/tests/test_evidence_planner.py` | `test_spl_generation_allows_spl_but_not_mcp` | **B** | Direct evidence_planner.plan_evidence authority | plan_evidence_from_canonical is sole planner entry | Call canonical adapter in test (item 17); green at `dcd5a3e` |
| 18 | `app/tests/test_evidence_planner_all_tier_grants.py` | `test_control_plane_off_stays_byte_identical` | **F** | control_plane_enabled=false preserves legacy grants | Control plane flag removed; canonical orchestration always runs | Remove cp_off branch; test canonical grant surface (item 17); green at `dcd5a3e` |
| 19 | `app/tests/test_golden_answer_runner_tier0.py` | `test_tier0_fixture_has_shared_control_plane_flow_refs` | **F** | Tier-0 fixtures reference control_plane_enabled flow | CP flag removed; fixtures reference canonical flow refs | Update fixture metadata (item 17); green at `dcd5a3e` |
| 20 | `app/tests/test_guided_answer_contract.py` | `test_live_pipeline_surfaces_guided_answer_contract_fields` | **G** | Guided answer contract fields on live response | Canonical guided lane surfaces same contract | Code fix: guided contract builder alignment (item 17); green at `dcd5a3e` |
| 21 | `app/tests/test_guided_hybrid_dispatch.py` | `test_flag_on_live_pipeline_uses_hybrid_dispatch` | **D** | Guided hybrid dispatch flag-on legacy path | Canonical guided_hybrid_dispatch after run_canonical_planning | Align dispatch predicate tests (item 17); green at `dcd5a3e` |
| 22 | `app/tests/test_guided_hybrid_dispatch.py` | `test_guided_safe_catalog_signed_reaches_mediated_execution_in_dispatch_node` | **D** | Guided hybrid dispatch flag-on legacy path | Canonical guided_hybrid_dispatch after run_canonical_planning | Align dispatch predicate tests (item 17); green at `dcd5a3e` |
| 23 | `app/tests/test_guided_hybrid_dispatch.py` | `test_guided_safe_catalog_unsigned_stays_inert_in_dispatch_node` | **D** | Guided hybrid dispatch flag-on legacy path | Canonical guided_hybrid_dispatch after run_canonical_planning | Align dispatch predicate tests (item 17); green at `dcd5a3e` |
| 24 | `app/tests/test_guided_hybrid_dispatch.py` | `test_uses_guided_hybrid_dispatch_from_state` | **D** | Guided hybrid dispatch flag-on legacy path | Canonical guided_hybrid_dispatch after run_canonical_planning | Align dispatch predicate tests (item 17); green at `dcd5a3e` |
| 25 | `app/tests/test_guided_hybrid_refinement.py` | `test_refinement_loop_stops_at_cap_and_trace_shows_rounds` | **G** | Guided hybrid refinement cap + trace | Refinement under canonical guided dispatch | Code fix: refinement trace under canonical path (item 17); green at `dcd5a3e` |
| 26 | `app/tests/test_guided_investigation_llm_firewall.py` | `test_firewall_guided_llm_success_mocked` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 27 | `app/tests/test_guided_investigation_llm_firewall.py` | `test_firewall_guided_llm_timeout_degraded` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 28 | `app/tests/test_guided_investigation_llm_firewall.py` | `test_resource_planner_firewall_skips_intent_advisor_when_guided_llm_on` | **C** | RP graph delegates through legacy bootstrap planning fork | rp_node_bootstrap uses run_canonical_planning only | Adjust RP graph test state seeding (item 17); green at `dcd5a3e` |
| 29 | `app/tests/test_guided_investigation_route.py` | `test_control_plane_off_keeps_guided_summary_notice_and_validation` | **F** | CP-off preserves guided notice path | Canonical-only runtime | Remove cp_off scenario (item 17); green at `dcd5a3e` |
| 30 | `app/tests/test_hybrid_role_graph.py` | `test_boundary_row_disables_all_llm_roles_including_shadow` | **F** | Hybrid role graph boundary row toggles CP/LLM flags | Removed flag surface; role graph tests need canonical posture | Rewrite boundary fixtures without control_plane_enabled (item 17); green at `dcd5a3e` |
| 31 | `app/tests/test_hybrid_role_graph.py` | `test_boundary_row_skips_composer_and_specialists` | **F** | Hybrid role graph boundary row toggles CP/LLM flags | Removed flag surface; role graph tests need canonical posture | Rewrite boundary fixtures without control_plane_enabled (item 17); green at `dcd5a3e` |
| 32 | `app/tests/test_hybrid_role_graph.py` | `test_investigation_row_enables_specialist_when_gaps_exist` | **F** | Hybrid role graph boundary row toggles CP/LLM flags | Removed flag surface; role graph tests need canonical posture | Rewrite boundary fixtures without control_plane_enabled (item 17); green at `dcd5a3e` |
| 33 | `app/tests/test_in_catalogue_contract_guard.py` | `test_full_guard_passes_against_baseline` | **B** | In-catalogue guard baseline from legacy planning path | Canonical known-lane produces contract fields | Refresh guard baseline after canonical routing (item 17); green at `dcd5a3e` |
| 34 | `app/tests/test_intent_advisor_consumer_gate.py` | `test_live_catalog_turn_records_no_consumer_skip` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 35 | `app/tests/test_intent_operation_bridge_shadow_stage3l_s2a1.py` | `test_bridge_compatible_when_primary_skill_observed` | **B** | Intent operation bridge on legacy planning surface | Bridge advisory after canonical route resolution | Re-anchor bridge tests post-canonical (item 17); green at `dcd5a3e` |
| 36 | `app/tests/test_intent_operation_bridge_shadow_stage3l_s2a1.py` | `test_bridge_incompatible_does_not_change_selected_skill` | **B** | Intent operation bridge on legacy planning surface | Bridge advisory after canonical route resolution | Re-anchor bridge tests post-canonical (item 17); green at `dcd5a3e` |
| 37 | `app/tests/test_intent_operation_bridge_shadow_stage3l_s2a1.py` | `test_chat_selected_skill_and_message_unchanged_with_bridge` | **B** | Intent operation bridge on legacy planning surface | Bridge advisory after canonical route resolution | Re-anchor bridge tests post-canonical (item 17); green at `dcd5a3e` |
| 38 | `app/tests/test_langgraph_shadow_phase12.py` | `test_failed_login_followed_by_success_parity` | **B** | Shadow graph uses graph_node_evidence_planning for planning node | shadow_node_planning calls run_canonical_planning (item 32) | Re-baseline shadow/imperative parity expectations (item 17); green at `dcd5a3e` |
| 39 | `app/tests/test_live_catalogue_router_probes.py` | `test_live_catalogue_router_probes[success_after_failure]` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 40 | `app/tests/test_live_catalogue_router_probes.py` | `test_live_catalogue_router_probes[typo_failed_login]` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 41 | `app/tests/test_llm_derived_spl_artifact_pipeline.py` | `test_execution_node_dispatches_by_risk_tier[low-True-executed]` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 42 | `app/tests/test_llm_derived_spl_artifact_pipeline.py` | `test_execution_node_dispatches_by_risk_tier[medium-False-requires_human_review]` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 43 | `app/tests/test_llm_primary_planning.py` | `test_in_catalogue_contract_guard_still_green` | **B** | LLM-primary planning via graph_node_evidence_planning | Canonical orchestrator + optional advisory only | Use run_canonical_planning / helper (item 16–17); green at `dcd5a3e` |
| 44 | `app/tests/test_llm_primary_planning.py` | `test_llm_unavailable_keeps_deterministic_plan` | **B** | LLM-primary planning via graph_node_evidence_planning | Canonical orchestrator + optional advisory only | Use run_canonical_planning / helper (item 16–17); green at `dcd5a3e` |
| 45 | `app/tests/test_llm_primary_planning.py` | `test_oos_promoted_plan_addition_drives_dispatch_order` | **B** | LLM-primary planning via graph_node_evidence_planning | Canonical orchestrator + optional advisory only | Use run_canonical_planning / helper (item 16–17); green at `dcd5a3e` |
| 46 | `app/tests/test_llm_primary_planning.py` | `test_promoted_plan_walk_reaches_added_step` | **B** | LLM-primary planning via graph_node_evidence_planning | Canonical orchestrator + optional advisory only | Use run_canonical_planning / helper (item 16–17); green at `dcd5a3e` |
| 47 | `app/tests/test_llm_route_plan_shadow_stage3k_q1f.py` | `test_chat_llm_shadow_candidate_does_not_change_analyst_answer` | **B** | Shadow route plan expects legacy planning trace | Canonical shadow_tail + planning_decision trace | Update shadow expectations (item 17); green at `dcd5a3e` |
| 48 | `app/tests/test_llm_route_plan_shadow_stage3k_q1f.py` | `test_chat_test_hook_still_works_when_llm_skipped` | **B** | Shadow route plan expects legacy planning trace | Canonical shadow_tail + planning_decision trace | Update shadow expectations (item 17); green at `dcd5a3e` |
| 49 | `app/tests/test_llm_route_plan_shadow_stage3k_q1f.py` | `test_lineage_includes_llm_route_plan_hop` | **B** | Shadow route plan expects legacy planning trace | Canonical shadow_tail + planning_decision trace | Update shadow expectations (item 17); green at `dcd5a3e` |
| 50 | `app/tests/test_mitre_decision_runtime.py` | `test_flag_off_finalize_keeps_legacy_use_case_mapping` | **F** | MITRE branch flag-off uses legacy mapping | Canonical finalize path always runs | Remove flag-off branch (item 17); green at `dcd5a3e` |
| 51 | `app/tests/test_mitre_evidence_branch_phase5b.py` | `test_cp_off_legacy_path_remains_compatible` | **F** | CP-off keeps legacy MITRE path | Canonical MITRE branch only | Retire cp_off test (item 17); green at `dcd5a3e` |
| 52 | `app/tests/test_mitre_spl_governance_gate_closure.py` | `test_legacy_paths_remain_when_new_flags_off` | **F** | New governance flags off restores legacy paths | Canonical path is sole authority | Update test to canonical-only expectations (item 17); green at `dcd5a3e` |
| 53 | `app/tests/test_narration_paths_parity.py` | `test_composer_enabled_requires_cp_and_both_flags` | **F** | Composer requires control_plane_enabled | CP flag removed; composer gating uses remaining flags | Rewrite prerequisite flags (item 17); green at `dcd5a3e` |
| 54 | `app/tests/test_p2_known_path_authority.py` | `test_allowlisted_known_path_surfaces_operation_authority` | **A** | P2 known-path authority assumes legacy routing mode | Canonical lane router owns known-path intent | Reconcile with canonical_planning_orchestrator (item 17); green at `dcd5a3e` |
| 55 | `app/tests/test_p2_known_path_authority.py` | `test_non_allowlisted_known_path_surfaces_fallback_without_applying` | **A** | P2 known-path authority assumes legacy routing mode | Canonical lane router owns known-path intent | Reconcile with canonical_planning_orchestrator (item 17); green at `dcd5a3e` |
| 56 | `app/tests/test_p2_ood_supporters_audit.py` | `test_novel_ood_candidate_stops_at_audit_hil` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 57 | `app/tests/test_p2_registry_authority_deprecation.py` | `test_p2_9_workflow_uses_mirrored_skill_for_spl_when_legacy_authority_disabled` | **A** | Legacy authority disable mirror still active | Canonical skill from routed/adjudication only | Remove legacy authority branch (item 17); green at `dcd5a3e` |
| 58 | `app/tests/test_p2a_narration_exclusivity.py` | `test_cp_off_allows_lab_narration_when_client_configured` | **F** | CP-off allows lab narration | Canonical-only runtime | Remove cp_off path (item 17); green at `dcd5a3e` |
| 59 | `app/tests/test_pipeline_dispatch_phase2a.py` | `test_pipeline_dispatch_attached_after_cp_on_evidence_planning` | **D** | Pipeline dispatch attached after evidence_planning node | Dispatch attaches after run_canonical_planning + planning_decision | Rewire dispatch attachment tests (item 17); green at `dcd5a3e` |
| 60 | `app/tests/test_pipeline_dispatch_phase2a.py` | `test_pipeline_dispatch_cp_off_stub_attached_when_v2_enabled` | **D** | Pipeline dispatch attached after evidence_planning node | Dispatch attaches after run_canonical_planning + planning_decision | Rewire dispatch attachment tests (item 17); green at `dcd5a3e` |
| 61 | `app/tests/test_pipeline_dispatch_phase2b.py` | `test_cp_off_synthetic_evidence_plan_builds_dispatch` | **D** | Dispatch v2 schedule from synthetic/cp_off evidence plan | Canonical evidence_plan from plan_evidence_from_canonical only | Use canonical flow helper (item 16–17); green at `dcd5a3e` |
| 62 | `app/tests/test_pipeline_dispatch_phase2b.py` | `test_live_data_spl_authoring_schedules_pre_mcp_not_execution` | **D** | Dispatch v2 schedule from synthetic/cp_off evidence plan | Canonical evidence_plan from plan_evidence_from_canonical only | Use canonical flow helper (item 16–17); green at `dcd5a3e` |
| 63 | `app/tests/test_pipeline_dispatch_phase2b.py` | `test_spl_authoring_with_index_skips_pre_mcp_but_includes_spl_chain` | **D** | Dispatch v2 schedule from synthetic/cp_off evidence plan | Canonical evidence_plan from plan_evidence_from_canonical only | Use canonical flow helper (item 16–17); green at `dcd5a3e` |
| 64 | `app/tests/test_pipeline_dispatch_phase6b.py` | `test_execute_plan_dispatch_calls_match_v2_schedule` | **D** | execute_plan_dispatch matches legacy v2 schedule table | Canonical dispatch schedule from planning_decision | Reconcile schedule with canonical_mode (item 17); green at `dcd5a3e` |
| 65 | `app/tests/test_planner_executor.py` | `test_blocked_registry_resource_step_is_never_dispatched` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 66 | `app/tests/test_planner_executor.py` | `test_dispatch_matches_legacy_live_branch_order` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 67 | `app/tests/test_planner_executor.py` | `test_dispatch_matches_legacy_rag_only_branch` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 68 | `app/tests/test_planner_executor.py` | `test_execute_plan_dispatch_does_not_use_guided_trace_hook_names` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 69 | `app/tests/test_planner_executor.py` | `test_execution_stage_always_runs_on_live_branch` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 70 | `app/tests/test_planner_executor.py` | `test_preblocked_mcp_preserves_skill_contract_reason_and_metadata` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 71 | `app/tests/test_planner_executor.py` | `test_preblocked_policy_mcp_step_still_runs_execution_gate` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 72 | `app/tests/test_planner_executor.py` | `test_v2_non_spl_schedule_does_not_synthesize_execution_without_workflow_plan` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 73 | `app/tests/test_planner_executor.py` | `test_walk_plan_steps_and_predicate_parity_on_live_plan` | **D** | Planner executor parity with legacy imperative branch order | execute_plan_dispatch under canonical non-planned guards | Update executor tests for canonical dispatch trace (item 17); green at `dcd5a3e` |
| 74 | `app/tests/test_precondition_evaluation_shadow_stage3l_s7.py` | `test_chat_includes_precondition_evaluation_without_changing_selected_skill` | **B** | Precondition shadow on legacy chat path | Canonical chat path with shadow_tail | Re-run against build_live_chat_response (item 17); green at `dcd5a3e` |
| 75 | `app/tests/test_q046_intent_advisor_latency.py` | `test_broad_guided_hunt_pr53_still_skips_and_routes_guided` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 76 | `app/tests/test_recipe_selection_live_wiring.py` | `test_in_catalogue_query_never_recipe_routed` | **B** | Recipe selection wired through graph_node_evidence_planning | Recipe routing after canonical planning + discovery loop | Rewire to canonical discovery seam (item 17); green at `dcd5a3e` |
| 77 | `app/tests/test_recipe_selection_live_wiring.py` | `test_natural_hunt_query_recipe_routes_without_matchpath_monkeypatch` | **B** | Recipe selection wired through graph_node_evidence_planning | Recipe routing after canonical planning + discovery loop | Rewire to canonical discovery seam (item 17); green at `dcd5a3e` |
| 78 | `app/tests/test_recipe_selection_live_wiring.py` | `test_out_of_registry_hunt_shape_with_grant_selects_a_recipe` | **B** | Recipe selection wired through graph_node_evidence_planning | Recipe routing after canonical planning + discovery loop | Rewire to canonical discovery seam (item 17); green at `dcd5a3e` |
| 79 | `app/tests/test_resource_plan_step_dispatch.py` | `test_cp_off_legacy_dispatch_source` | **D** | Resource plan step dispatch from cp_off legacy source | Canonical plan_dispatch_trace only | Remove cp_off dispatch source (item 17); green at `dcd5a3e` |
| 80 | `app/tests/test_resource_plan_step_dispatch.py` | `test_execute_plan_dispatch_records_step_walk_trace` | **D** | Resource plan step dispatch from cp_off legacy source | Canonical plan_dispatch_trace only | Remove cp_off dispatch source (item 17); green at `dcd5a3e` |
| 81 | `app/tests/test_resource_planner_dry_runs.py` | `test_resource_planner_graph_typo_parity` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 82 | `app/tests/test_resource_planner_graph_skeleton.py` | `test_resource_planner_governance_nodes_are_reachable` | **C** | RP graph reachability without non_planned_finalize short-circuit | non_planned_finalize → finalize edge for non-planned outcomes (item 32) | Update reachability map for new node/edges (item 17); green at `dcd5a3e` |
| 83 | `app/tests/test_route_authority_gate_stage3l_s3_3a.py` | `test_a_bridge_incompatible_preserves_selected_skill` | **A** | Route authority gate assumes pre-canonical skill selection mode | Canonical route adjudication is authority; gate is advisory overlay | Align gate tests with canonical route_contract (item 17); green at `dcd5a3e` |
| 84 | `app/tests/test_route_authority_gate_stage3l_s3_3a.py` | `test_b_validator_blocks_preserves_selected_skill` | **A** | Route authority gate assumes pre-canonical skill selection mode | Canonical route adjudication is authority; gate is advisory overlay | Align gate tests with canonical route_contract (item 17); green at `dcd5a3e` |
| 85 | `app/tests/test_route_authority_gate_stage3l_s3_3a.py` | `test_c_not_on_allowlist_preserves_selected_skill` | **A** | Route authority gate assumes pre-canonical skill selection mode | Canonical route adjudication is authority; gate is advisory overlay | Align gate tests with canonical route_contract (item 17); green at `dcd5a3e` |
| 86 | `app/tests/test_route_authority_gate_stage3l_s3_3a.py` | `test_d_global_kill_switch_preserves_selected_skill` | **A** | Route authority gate assumes pre-canonical skill selection mode | Canonical route adjudication is authority; gate is advisory overlay | Align gate tests with canonical route_contract (item 17); green at `dcd5a3e` |
| 87 | `app/tests/test_route_authority_gate_stage3l_s3_3a.py` | `test_e_missing_threshold_ref_fallback_never_applies_authority` | **A** | Route authority gate assumes pre-canonical skill selection mode | Canonical route adjudication is authority; gate is advisory overlay | Align gate tests with canonical route_contract (item 17); green at `dcd5a3e` |
| 88 | `app/tests/test_route_authority_step3_stage3l_s3.py` | `test_happy_path_authority_applied_only_with_explicit_lab_config` | **A** | Step-3 authority assumes canonical can be bypassed | Canonical routing owns selected_skill | Update authority application preconditions (item 17); green at `dcd5a3e` |
| 89 | `app/tests/test_route_authority_step3_stage3l_s3.py` | `test_missing_threshold_ref_never_defaults_authority` | **A** | Step-3 authority assumes canonical can be bypassed | Canonical routing owns selected_skill | Update authority application preconditions (item 17); green at `dcd5a3e` |
| 90 | `app/tests/test_route_plan_stage3k_r2.py` | `test_chat_behavior_unchanged_with_route_plan_shadow` | **B** | Route plan shadow on legacy evidence planning path | Shadow enrichment after run_canonical_planning | Update trace anchors (item 17); green at `dcd5a3e` |
| 91 | `app/tests/test_route_plan_stage3k_r2.py` | `test_mock_candidate_validation_path_is_observational` | **B** | Route plan shadow on legacy evidence planning path | Shadow enrichment after run_canonical_planning | Update trace anchors (item 17); green at `dcd5a3e` |
| 92 | `app/tests/test_run_contract_builder.py` | `test_cp_off_uses_routing_resolution_not_adjudication` | **F** | CP-off reads routing_skill_resolution not adjudication | Canonical always uses adjudicated route contract | Retire cp_off assertion (item 17); green at `dcd5a3e` |
| 93 | `app/tests/test_skill_focus_probes.py` | `test_cross_skill_live_has_three_legs` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 94 | `app/tests/test_soc_clean_answer_eval.py` | `test_auth_failed_login_spike_spl_preamble_appears_once` | **E** | Clean-answer eval expects SPL preamble shape from partial clarification evidence_plan | Clarification path has no EvidencePlan; analyst sections from outcome only | Refresh eval assertion for canonical clarification surface (item 17); green at `dcd5a3e` |
| 95 | `app/tests/test_spl_generation_live_scenarios.py` | `test_template_query_renders_governed_auth_failed_login_spike` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 96 | `app/tests/test_spl_optimization_stage3jk0.py` | `test_provider_pipeline_returns_optimized_candidate_and_normalized_spl` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 97 | `app/tests/test_spl_optimization_stage3jk0.py` | `test_provider_pipeline_validation_payload_surfaces_optimization_steps` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 98 | `app/tests/test_spl_slot_binding_validator.py` | `test_candidate_spl_stage_slot_binding_is_flag_gated` | **F** | Slot binding gated by removed dispatch flag | Canonical dispatch always runs slot binding policy | Update flag reference (item 17); green at `dcd5a3e` |
| 99 | `app/tests/test_t2_advisor_latency_hardening.py` | `test_advisory_trace_surfaces_latency_fields_on_live_path` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |
| 100 | `app/tests/test_utility_spl_llm_authoring.py` | `test_live_response_surfaces_utility_mode_and_postprocessor_trace` | **G** | Live behaviour drift under canonical-only runtime | Production canonical path must preserve governed behaviour | Code/test fix under item 17; green at `dcd5a3e` |

---

## Population B — Stale sentinel identity (1)

**Outside A–G totals** — no A–G definition accurately applies; this was a stale recorded failure identity, not a live canonical defect.

| Test identity | Nature | Evidence |
|---------------|--------|----------|
| `app/tests/test_eval_sentinel_runner.py::test_repo_baseline_matches_current_pipeline` | Stale guard-baseline identity captured before the sentinel re-freeze (Gate 1, Item 14). The test passes even with Item 31 changes stashed — it was listed as failing due to an outdated failure-count baseline, not because canonical planning was broken. | Commit `7a0c87c` documents the 112→111 guard-baseline correction: *"test_repo_baseline_matches_current_pipeline passes with this change stashed too; the guard baseline had one stale identity captured before the sentinel re-freeze."* Not an Item 31 production fix. |

---

## Population C — Historical identities not preserved (11)

**Exact test identities cannot be recovered authoritatively.** Per-identity categories are **not assigned** and test names are **not invented**.

### Commit-range forensics (`8792338`..`2fce033`)

| Commit | Production behaviour change | Pre-existing test edits |
|--------|----------------------------|-------------------------|
| `e3607a8` | No | No (new evaluator tests only) |
| `7a0c87c` | No | No (new projection tests only) |
| `48a217d` | **Yes** — unified production entry points via `run_canonical_planning` | No |
| `2fce033` | No | No (new AST/graph guard tests only) |

**Attribution:** The 11 dropped identities (112 − 1 stale sentinel − 100 captured = 11) are attributed at the **group level** to production commit `48a217d`, because it is the only commit in the range that changed production behaviour without editing pre-existing tests. These failures likely cleared as a side effect of runtime unification before the Item 15 enumeration ran.

### Four affected architectural surfaces (`48a217d`)

| Surface | Module | Change |
|---------|--------|--------|
| 1. Shared planning seam | `backend/app/chat/canonical_planning_orchestrator.py` | Introduced `run_canonical_planning(state)` as the single lane → route → planning_decision entry |
| 2. Imperative `/chat` pipeline | `backend/app/chat/pipeline.py` | `_run_live_chat_pipeline` calls the shared seam |
| 3. Resource Planner graph | `backend/app/graph/resource_planner_graph.py` | `rp_node_bootstrap` calls the same seam; `non_planned_finalize` blocks non-planned outcomes from SPL/execution |
| 4. Shadow graph wrapper | `backend/app/graph/planner_led_shadow_graph.py` | Shadow planning node delegates to `run_canonical_planning`; seeds session context like imperative |

**Limitation:** This is group-level attribution to the unification commit and the four surfaces above. Individual test names, failure modes, and A–G categories for these 11 identities are **not reconstructed**.

---

## Operational closure

With this derived inventory committed and the plan evidence corrected:

- **Item 15** — operationally closed with disclosed historical limitation (100 individually classified + 1 stale sentinel + 11 group-attributed)
- **Item 17** — operationally closed (`4358 passed, 0 failed` at HEAD)
- **Item 18a** — not started (per stop instruction)

