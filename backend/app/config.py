import os
import sys

import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

# ``env_file`` is resolved relative to the current working directory, so running
# pytest from the repo root would load the all-on production ``.env`` and flip
# default-off flags, breaking tests that assert default posture. Under pytest we
# ignore ``.env`` entirely so the suite is deterministic regardless of CWD. Set
# ``AI_SOC_DISABLE_DOTENV=1`` to force the same behavior outside pytest.
_DISABLE_DOTENV = "pytest" in sys.modules or os.getenv("AI_SOC_DISABLE_DOTENV") == "1"
_ENV_FILE: str | None = None if _DISABLE_DOTENV else ".env"


# Telemetry sink values that are wired up today. ``splunk`` and ``both`` are
# reserved for a future Splunk telemetry connector; until that connector
# lands the config layer rejects them at startup (see ``_validate``).
SUPPORTED_TELEMETRY_SINKS: tuple[str, ...] = ("db", "file", "none")
PLANNED_TELEMETRY_SINKS: tuple[str, ...] = ("splunk", "both")

# Governed LLM layer modes (Stage 3J-B). No mode triggers a real LLM call yet.
SUPPORTED_AI_SOC_LLM_MODES: tuple[str, ...] = (
    "mock",
    "local",
    "openai_compatible",
    "cisco_foundation_sec",
    "disabled",
)

SUPPORTED_ROUTING_MODES: tuple[str, ...] = (
    "deterministic_only",
    "llm_shadow_only",
    "llm_assisted_semantic",
    "llm_primary_lab",
)

# P0-9: flow-check profile label only — does not change runtime behavior until wired.
SUPPORTED_AI_SOC_FLOW_CHECK_MODES: tuple[str, ...] = ("", "stub_evidence")


class ConfigError(RuntimeError):
    """Raised on unsupported or unsafe configuration values."""


def parse_cors_allowed_origins(raw: str) -> list[str]:
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    if not origins:
        raise ConfigError("AI_SOC_CORS_ALLOWED_ORIGINS must include at least one origin.")
    return origins


class Settings(BaseSettings):
    app_env: str = "development"
    backend_port: int = 8010
    frontend_port: int = 3010
    ai_soc_cors_allowed_origins: str = "http://localhost:3010,http://127.0.0.1:3010"

    # Default matches the Docker Compose `postgres` service hostname and the
    # placeholder password used by `.env.example`. Production deployments
    # MUST override DATABASE_URL via env vars and never rely on this default.
    # This default is intentionally a dev placeholder, never a real secret.
    database_url: str = "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant"

    splunk_mcp_enabled: bool = True
    ai_soc_environment_mode: str = "coe"
    # Deployment profile id (coe | development). Compose loads env/profiles/<id>.env.example.
    ai_soc_env_profile: str = "coe"
    splunk_mcp_server_id: str = "splunk_soc"
    splunk_mcp_discovery_mode: str = "dynamic"
    splunk_ai_assistant_mode: str = "auto"
    splunk_saia_tools_enabled: bool = True
    splunk_use_saia_generate_spl: bool = True
    splunk_use_saia_explain_spl: bool = True
    splunk_use_saia_optimize_spl: bool = True
    splunk_use_saia_ask_question: bool = True
    splunk_saia_require_discovery: bool = True
    splunk_allow_run_saved_search: bool = False
    splunk_run_saved_search_require_hil: bool = True
    splunk_allowed_saved_searches: str = ""
    ai_soc_catalogue_auto_execute_enabled: bool = False
    # Item 6.2 — surface pending action proposals on /chat (default off; approve/deny via /api/actions).
    ai_soc_action_lane_live_proposals_enabled: bool = False
    splunk_run_query_require_validation: bool = True
    splunk_metadata_discovery_allowed: bool = True
    splunk_knowledge_object_discovery_allowed: bool = True
    splunk_allowed_core_tools: str = "splunk_run_query,splunk_get_info,splunk_get_indexes,splunk_get_index_info,splunk_get_metadata,splunk_get_user_info,splunk_get_knowledge_objects"
    splunk_allowed_saia_tools: str = "saia_generate_spl,saia_explain_spl,saia_optimize_spl,saia_ask_splunk_question"
    splunk_mcp_base_url: str = ""
    splunk_mcp_token: str = ""
    # Externally supplied secret reference (file mount). Never a hardcoded token.
    splunk_mcp_token_file: str = ""
    # TLS for the existing streamable_http transport. Default verify-on.
    splunk_mcp_tls_verify: bool = True
    splunk_mcp_ca_cert_path: str = ""
    splunk_mcp_connect_timeout_seconds: int = 10
    ai_soc_mcp_connection_store_path: str = ""
    llm_enabled: bool = False
    foundation_sec_instruct_url: str = ""
    foundation_sec_reasoning_url: str = ""
    reasoning_enabled: bool = False
    routing_mode: str = "llm_assisted_semantic"
    routing_lab_llm_primary_enabled: bool = False
    debug_trace_enabled: bool = True
    ai_soc_debug_api_enabled: bool = True
    ai_soc_debug_api_user_allowlist: str = ""
    ai_soc_debug_api_allow_any_authenticated: bool = False
    app_auth_role: str = "demo_analyst"
    app_auth_users_path: str = ""
    routing_deterministic_threshold: float = 0.70
    routing_llm_shadow_enabled: bool = True

    # Batch 1 — mock-MCP execution HIL hardening. A valid SPL and a successful
    # mock execution must never imply autonomous execution: by default a mock
    # success surfaces an analyst-review requirement. The without-HIL relaxation
    # applies ONLY when the deployment is explicitly flagged as demo/lab AND the
    # allow flag is set — two independent axes, so enabling a demo cannot
    # silently disable HIL on a non-demo deployment.
    ai_soc_require_hil_for_mock_execution: bool = True
    ai_soc_allow_mock_execution_without_hil_in_demo: bool = True
    ai_soc_demo_or_lab_execution_mode: bool = False
    # Require analyst confirm-or-update before splunk_run_query executes (after policy gates pass).
    ai_soc_require_spl_execution_confirmation: bool = True
    ai_soc_llm_shadow_narration_enabled: bool = False
    ioc_registry_enabled: bool = False
    ioc_registry_path: str = ""
    detection_registry_enabled: bool = False
    detection_registry_path: str = ""
    # WS-G offline ATT&CK/ATLAS STIX resolver (plan §15). Default-off, fail-closed:
    # unset/missing path -> resolver returns None (no names), exactly as today. These
    # are path vars, not a posture flag; MCP-execution + all-on SOC posture unchanged.
    ai_soc_attack_stix_path: str = ""
    ai_soc_atlas_stix_path: str = ""
    # WS-G offline ATT&CK Excel + ATLAS YAML resolver (the vendored, zero-extra-dep
    # backend; preferred over STIX when present). Default to the vendored repo paths;
    # missing file -> resolver returns None, fail-closed. Path vars, not posture flags.
    ai_soc_attack_xlsx_path: str = "docs/evals/enterprise-attack-v19.1.xlsx"
    ai_soc_atlas_yaml_path: str = "docs/threat-intel/atlas/raw/ATLAS.yaml"
    # WS-A CVE snapshot read model (plan §3 A5). Default-off, fail-closed.
    ai_soc_cve_snapshot_dir: str = ""
    ai_soc_cve_snapshot_stale_after_days: int = 30
    # NVD API key for the connected-zone CVE snapshot builder (operator tooling only;
    # never used by the air-gapped runtime). Registered so the .env value loads cleanly.
    nvd_api_key: str = ""
    routing_compare_logging_enabled: bool = True
    # Stage 3L-S3 Steps 1–2: shadow compare envelope only (no route authority change).
    route_authority_compare_enabled: bool = True
    route_authority_operation_authoritative_enabled: bool = False
    route_authority_operation_coverage_allowlist: str = ""
    # P2-open: structural validation for non-seed primary_skill (lab/shadow).
    route_plan_open_operations_enabled: bool = True
    # P2-9: when false and operation authority applied, workflow uses registry operation mirror.
    legacy_selected_skill_authority_enabled: bool = True
    # P2-supporter: run read-only supporters during route-plan sidecar (not post-hoc only).
    route_plan_supporters_runtime_enabled: bool = True
    # P2-audit: persist operation audit rows to in-process store + telemetry.
    operation_audit_persistence_enabled: bool = True
    quality_review_enabled: bool = False
    quality_review_user_allowlist: str = ""
    quality_review_allow_any_authenticated: bool = False
    mcp_mode: str = "mock"
    mcp_servers: str = ""
    mcp_default_server: str = "splunk_soc"
    mcp_global_execution_enabled: bool = False
    mcp_server_mock_execution_enabled: bool = False
    # Read-only discovery tools (indexes/metadata). Separate from search execution flags.
    mcp_discovery_enabled: bool = True
    # Step 3 — async Splunk search job lifecycle bounds (connector-internal).
    # A submit + bounded polls is ONE logical investigation call.
    mcp_max_polls_per_call: int = 60
    mcp_search_job_timeout_ms: int = 120000
    mcp_search_poll_interval_ms: int = 2000
    rag_mode: str = "mock"
    soc_kb_retrieval_enabled: bool = False
    soc_kb_collections_path: str = "backend/app/knowledge/fixtures/soc_kb_collections.json"
    soc_kb_documents_path: str = "backend/app/knowledge/fixtures/soc_kb_documents.json"
    soc_kb_entries_path: str = "backend/app/knowledge/fixtures/soc_kb_entries.json"
    soc_kb_import_batches_path: str = "backend/app/knowledge/fixtures/soc_kb_import_batches.json"
    soc_kb_allowed_statuses: str = "active,published"
    soc_kb_approved_statuses: str = "coe_reviewed,pgcil_approved"
    soc_kb_include_drafts: bool = False
    soc_kb_include_superseded: bool = False
    soc_kb_environment: str = "coe"
    soc_kb_max_results: int = 5
    soc_kb_min_confidence: float = 0.35
    soc_kb_retrieval_mode: str = "deterministic"
    soc_kb_repository_backend: str = "json"
    soc_kb_vector_backend: str = "none"
    soc_kb_reranker_enabled: bool = False
    soc_kb_graph_expansion_enabled: bool = False
    soc_kb_hybrid_alpha: float = 0.5
    soc_kb_vector_model: str = "BAAI/bge-m3"
    soc_kb_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    soc_kb_embedding_indexing_enabled: bool = False
    soc_kb_direct_to_llm: bool = False
    soc_kb_llm_selection_enabled: bool = False
    soc_kb_llm_ambiguity_assist_enabled: bool = False
    soc_kb_hybrid_placeholder_enabled: bool = True
    soc_kb_graph_placeholder_enabled: bool = True
    # Stage 3G.1 reranker connector. Disabled by default; mock/no-op unless a real
    # provider is configured. Secrets are never surfaced in status output.
    soc_kb_reranker_provider: str = "mock"
    soc_kb_reranker_base_url: str = ""
    soc_kb_reranker_api_key: str = ""
    soc_kb_reranker_timeout_seconds: int = 10
    soc_kb_reranker_top_n: int = 5
    # Stage 3G.1 candidate-constrained LLM ambiguity assist. Disabled by default;
    # provider resolves through the LLM registry and only sees eligible candidates.
    soc_kb_llm_ambiguity_provider: str = ""
    soc_kb_llm_ambiguity_max_candidates: int = 5
    llm_mode: str = "mock"
    llm_providers: str = ""
    llm_default_provider: str = "mock"
    llm_router_provider: str = "mock"
    llm_synthesis_provider: str = "mock"
    llm_reasoning_provider: str = ""
    llm_teacher_provider: str = ""
    llm_concurrency_per_provider: int = 2
    llm_global_concurrency: int = 4
    llm_timeout_seconds: int = 30
    llm_health_canary_enabled: bool = False
    llm_tool_recommendation_enabled: bool = False

    # Stage 3J-B governed LLM layer. This is the configuration/readiness surface
    # for the upcoming evidence-based synthesis stage. NOTHING here calls a real
    # LLM yet; these are flags and placeholders only. `ai_soc_llm_mode` is the
    # canonical on/off: mode "disabled" forces the governed layer off regardless
    # of `ai_soc_llm_enabled`.
    ai_soc_llm_enabled: bool = False
    ai_soc_llm_mode: str = "mock"
    ai_soc_llm_allow_cloud: bool = False
    ai_soc_llm_airgap_enforced: bool = False
    ai_soc_llm_default_provider: str = ""
    ai_soc_llm_default_model: str = ""
    # Direct-LLM lab model selection (advisory/display only — does NOT hot-swap the
    # llama-server, which loads the model pinned in its systemd unit). The active
    # label and the comma-separated allowlist are surfaced by the Ask LLM page so an
    # operator can record/see the intended target.
    ai_soc_llm_active_model: str = "foundation-sec-1.1-8b-instruct-q8_0"
    ai_soc_llm_available_models: str = "foundation-sec-1.1-8b-instruct-q8_0"
    # Optional path for the UI-editable LLM connection override store (api key
    # included → keep off git). Blank = backend/data/llm_connection.json.
    ai_soc_llm_connection_store_path: str = ""
    ai_soc_llm_timeout_seconds: int = 30
    # Protected wall-time reserve for the intent advisor hop (not the full sidecar timeout).
    ai_soc_llm_intent_advisor_reserve_seconds: float = 12.0
    # Wall-clock ceiling for all blocking LLM calls on a single /chat turn. Caps the
    # stacked-sidecar latency on the slow on-prem model so a turn cannot hang 70-160s;
    # the deterministic answer always ships. 0 disables the gate.
    ai_soc_llm_turn_deadline_seconds: float = 75.0
    # Non-frozen-T0 / T2 / out-of-registry review-only: cap intent advisor wall-clock
    # and overall turn budget so a slow on-prem model cannot block /chat 60–120s.
    ai_soc_llm_t2_intent_advisor_bound_seconds: float = 25.0
    ai_soc_llm_t2_turn_deadline_seconds: float = 45.0
    ai_soc_llm_max_input_tokens: int = 8000
    ai_soc_llm_max_output_tokens: int = 1024
    ai_soc_llm_temperature: float = 0.2
    ai_soc_llm_streaming: bool = False
    ai_soc_llm_log_prompts: bool = False
    ai_soc_llm_log_responses: bool = False
    ai_soc_llm_redact_secrets: bool = True
    # Role -> provider/model mappings for the governed layer.
    ai_soc_llm_role_synthesis_provider: str = ""
    ai_soc_llm_role_synthesis_model: str = ""
    ai_soc_llm_role_reasoning_provider: str = ""
    ai_soc_llm_role_reasoning_model: str = ""
    ai_soc_llm_role_router_provider: str = ""
    ai_soc_llm_role_router_model: str = ""
    ai_soc_llm_intent_provider: str = ""
    ai_soc_llm_intent_model: str = ""
    # Planner-led Phase 2: early intent advisor. Advisory only, default off.
    ai_soc_llm_intent_advisor_enabled: bool = False
    # Planner-led Phase 3: path/tool selection node. Schedules branches only; default off.
    ai_soc_planner_path_selection_enabled: bool = False
    # Planner-led Phase 5B: MITRE evidence-status branch authority. Default off.
    ai_soc_planner_mitre_branch_enabled: bool = False
    # Planner-led Phase 6: runtime SPL template governance. Default off.
    ai_soc_spl_template_governance_enabled: bool = False
    # Lab-only SPL draft preview when governed template/source profile is unavailable. Default off.
    ai_soc_spl_draft_preview_enabled: bool = False
    # T2 answer-shape router + signal-class guidance (WS-0/WS-1). Default off.
    ai_soc_t2_answer_shape_enabled: bool = False
    # T2 answer surfacing — expose SPL drafts in analyst card (WS-2). Default off.
    ai_soc_t2_answer_surfacing_enabled: bool = False
    # T2 RAG/playbook surfacing — render SOC-KB steps on knowledge turns (WS-7a). Default off.
    ai_soc_t2_rag_surfacing_enabled: bool = False
    # Phase 4/5: curated enrichment activation for runtime evidence/planner paths. Default off.
    ai_soc_curated_enrichment_activation_enabled: bool = False
    # S3 master-plan alias: runtime enrichment loader gate (default off; OR with curated flag).
    ai_soc_runtime_enrichment_enabled: bool = False
    ai_soc_llm_reasoning_provider: str = ""
    ai_soc_llm_reasoning_model: str = ""
    ai_soc_llm_synthesis_provider: str = ""
    ai_soc_llm_synthesis_model: str = ""
    ai_soc_llm_spl_advisory_provider: str = ""
    ai_soc_llm_spl_advisory_model: str = ""
    ai_soc_llm_spl_fallback_enabled: bool = False
    # PR #58 — bounded SPL draft for explicit universal/template-free utility authoring
    # only (not global SPL failover). Scoped hop; deterministic skeleton fallback.
    ai_soc_llm_utility_spl_draft_enabled: bool = True
    # Slow on-prem VPS: sub-10s timeouts are ineffective; 90s is the operator default.
    ai_soc_llm_utility_spl_draft_timeout_seconds: float = 90.0
    ai_soc_llm_utility_spl_draft_failover_enabled: bool = False
    # When false, universal utility SPL still runs intent advisor (use if route unsure).
    ai_soc_llm_utility_skip_intent_advisor: bool = True
    # Optional explicit COE default for generic/template-free utility SPL.
    ai_soc_utility_spl_default_index: str = ""
    # Regenerate-once on the SPL failover relevance gate. Default off: one LLM call
    # per failover turn so slow on-prem hardware does not double worst-case latency.
    ai_soc_llm_spl_failover_retry_enabled: bool = False
    # Optional JSON map of placeholder stem -> index/sourcetype value for Phase H0.
    ai_soc_source_profile_map: str = ""
    # WS2 prototype: resolve <stem> placeholders in governed template SPL from the
    # Environment Knowledge map (load_static_source_profile) at render time, so
    # index/sourcetype come from Environment Knowledge instead of being hardcoded.
    # Activated (WS2): governed templates carry <stem> placeholders that resolve to
    # index/sourcetype from Environment Knowledge at render time, so the deployment
    # map is the single source of truth. Resolution yields the same SPL the
    # templates emitted when hardcoded (verified byte-identical round-trip). No-op
    # on templates without placeholders (aws/tstats/scada/cisco stay concrete).
    ai_soc_template_env_binding_enabled: bool = True
    # Persisted COE source profile map (Settings UI). Empty = backend/data/source_profile_map.json
    ai_soc_source_profile_store_path: str = ""
    ai_soc_asset_registry_store_path: str = ""
    ai_soc_llm_template_match_provider: str = ""
    ai_soc_llm_template_match_model: str = ""
    ai_soc_llm_template_render_provider: str = ""
    ai_soc_llm_template_render_model: str = ""
    ai_soc_llm_route_plan_provider: str = ""
    ai_soc_llm_route_plan_model: str = ""
    ai_soc_llm_analyst_summary_narration_provider: str = ""
    ai_soc_llm_analyst_summary_narration_model: str = ""
    ai_soc_llm_guard_provider: str = ""
    ai_soc_llm_guard_model: str = ""
    # P5: MITRE candidate mapper sidecar (review-queue only; never authoritative).
    ai_soc_llm_mitre_candidate_mapping_enabled: bool = False
    ai_soc_llm_mitre_candidate_provider: str = ""
    ai_soc_llm_mitre_candidate_model: str = ""
    # Provider endpoint placeholders. Secrets are never surfaced in status.
    ai_soc_llm_openai_base_url: str = ""
    ai_soc_llm_openai_api_key: str = ""
    ai_soc_llm_openai_model: str = ""
    ai_soc_llm_foundation_sec_instruct_base_url: str = ""
    ai_soc_llm_foundation_sec_instruct_api_key: str = ""
    ai_soc_llm_foundation_sec_instruct_model: str = ""
    ai_soc_llm_foundation_sec_reasoning_base_url: str = ""
    ai_soc_llm_foundation_sec_reasoning_api_key: str = ""
    ai_soc_llm_foundation_sec_reasoning_model: str = ""
    ai_soc_llm_local_base_url: str = ""
    ai_soc_llm_local_api_key: str = ""
    ai_soc_llm_local_model: str = ""
    # Operator LLM service control from the UI/API. The backend runs in Docker and
    # cannot ``systemctl`` the host llama-server directly: when enabled, a control
    # request is written as a sentinel file into ``ai_soc_llm_control_dir`` (a shared
    # volume) and a host watcher (``scripts/llm_control_watcher.py``) applies it.
    # Default OFF — this is a privileged control surface.
    ai_soc_llm_control_enabled: bool = False
    ai_soc_llm_control_dir: str = ""
    # COE Qwen 2.5 72B — prepended to the failover chain when true and QWEN_* are set.
    # Default false: dev/staging uses LOCAL_* (Foundation-Sec) + Instruct failover only.
    ai_soc_llm_qwen_primary_enabled: bool = False
    ai_soc_llm_qwen_base_url: str = ""
    ai_soc_llm_qwen_api_key: str = ""
    ai_soc_llm_qwen_model: str = ""
    # MCP tool-planner role: Foundation-Sec Instruct is the planner (1-LLM decision,
    # 2026-06-15). Qwen is OFF by default and only appended as a *failover* after
    # Instruct when this flag is on AND the QWEN_* endpoint is configured.
    ai_soc_llm_planner_qwen_failover_enabled: bool = False
    # Evidence-gating governance for the upcoming synthesis stage.
    ai_soc_llm_require_context_sufficiency: bool = True
    ai_soc_llm_require_source_refs: bool = True
    ai_soc_llm_allow_insufficient_evidence_response: bool = False
    # Hard kill-switches. Default false; no synthesis or answer guard exists yet.
    ai_soc_llm_final_synthesis_enabled: bool = False
    ai_soc_llm_answer_guard_enabled: bool = False
    # S6c — lab-only Answer Guard alias (OR with ai_soc_llm_answer_guard_enabled).
    ai_soc_answer_guard_lab_enabled: bool = False
    # When true (and final synthesis is on, mode is not mock/disabled, and a
    # local/openai-compatible endpoint is configured), the live-chat synthesis
    # narrates the analyst summary with the real model instead of the
    # deterministic lab draft. Defaults false so the test suite and the
    # Experience Center fixture path never make a live model call.
    ai_soc_llm_live_synthesis_enabled: bool = False
    # Phase 2.5 — weak-case composition HIL: below this confidence, attach
    # analyst_review_required while still rendering the composed body.
    ai_soc_llm_compose_hil_threshold: float = 0.55

    # Stage 3M-S4: Experience Center demo-only LLM shadow (lineage/trace; no final synthesis).
    demo_llm_shadow_enabled: bool = False
    demo_llm_shadow_provider: str = "disabled"
    demo_llm_shadow_model: str = ""
    demo_llm_shadow_endpoint: str = ""
    demo_llm_shadow_timeout_seconds: int = 5
    # RETIRED (flag rightsizing Batch A, 2026-07-03): read nowhere in the codebase.
    # Field kept one release so a .env that still sets it degrades to the logged
    # warning in _validate instead of a config crash — dotenv keys hit pydantic's
    # extra=forbid, unlike process-env vars which are silently ignored.
    ai_soc_flow_check_mode: str = ""
    # When true, /chat returns the same governed payload as Experience Center when the
    # user message exactly matches a demo scenario query (normalized). Does not enable
    # real Splunk MCP or live Foundation-sec calls.
    ai_soc_live_chat_ec_parity_enabled: bool = False
    # LangGraph Resource Planner graph is the production /chat spine (default on).
    langgraph_orchestration_enabled: bool = True
    # Phase 12: planner-led fan-out/fan-in shadow graph for tests/trace only (default off).
    ai_soc_langgraph_shadow_enabled: bool = False
    # Two-stage pipeline dispatch authority (intent_dispatch + pipeline_dispatch).
    # Default false until Phase 8 green; operator .env may set true for on-host probes.
    ai_soc_pipeline_dispatch_v2_enabled: bool = False
    # Guided hybrid investigation execution rail (committed ResourcePlan only).
    ai_soc_guided_hybrid_investigation_enabled: bool = False
    # Plan 2 C0 (`EXECUTION-DRIVEN`, approved 2026-08-11): compile the dispatch
    # schedule from the committed ResourcePlan's execution contract instead of
    # the fixed predicate schedule. Default false; the exact name was approved
    # in the C0 decision record and may not be renamed or defaulted on.
    ai_soc_resource_plan_execution_enabled: bool = False
    # Plan 5 B4: bounded T4 semantic understanding hop. Default false. T1–T3 never
    # invoke it. Timeout/error keeps the deterministic ResolvedQueryContract.
    # The 2.0s default is a code fallback, not a COE qualification value. COE
    # profile + T4-on requires an explicit operator override (see `_validate`).
    ai_soc_t4_semantic_understanding_enabled: bool = False
    ai_soc_t4_semantic_understanding_timeout_seconds: float = 2.0
    # Plan 5 B5: live fail-closed capability enforcement from ResolvedQueryContract.
    # Default false. Activation is a named STOP gate (B_LIVE_CAPABILITY_ENFORCEMENT).
    ai_soc_live_capability_enforcement_enabled: bool = False
    # Canonical handoff durable store TTL (PostgreSQL).
    ai_soc_handoff_store_ttl_minutes: int = 60
    # Item 28 — bounded retention purge for canonical_handoffs / canonical_planning_events.
    ai_soc_canonical_retention_purge_enabled: bool = True
    ai_soc_canonical_retention_purge_interval_seconds: int = 3600
    ai_soc_canonical_retention_purge_batch_size: int = 500
    ai_soc_canonical_handoff_retention_grace_hours: int = 24
    ai_soc_canonical_planning_event_diagnostic_retention_days: int = 7
    ai_soc_canonical_planning_event_audit_retention_days: int = 90
    ai_soc_guided_max_duplicate_tool_calls: int = 1
    # Guided read-only MCP discovery lane (metadata tools only; no run_query/SPL execution).
    # Default false — flag-off preserves legacy guided_investigation byte-identical behavior.
    ai_soc_guided_mcp_discovery_enabled: bool = False
    ai_soc_guided_llm_enabled: bool = False
    ai_soc_guided_llm_timeout_seconds: float = 120.0
    ai_soc_guided_llm_min_final_reserve_seconds: float = 90.0
    ai_soc_guided_llm_intent_advisor_timeout_seconds: float = 15.0
    ai_soc_guided_llm_max_calls: int = 1
    # Batch 5 — lightweight investigation session pins (structured only, no transcript).
    ai_soc_session_context_enabled: bool = True
    ai_soc_session_context_ttl_minutes: int = 30
    # S6d — durable session pin store backend: memory (default) or file.
    ai_soc_session_store_backend: str = "memory"
    ai_soc_session_store_file_dir: str = "/tmp/ai_soc_session_pins"
    # S5 — split live route skill from planning skill (trace-only; default off).
    ai_soc_pipeline_split_routing_nodes_enabled: bool = False

    embeddings_mode: str = "mock"
    telemetry_mode: str = "db"
    spl_validation_enabled: bool = True
    spl_allowed_indexes: str = "pgcil_soc"
    spl_allowed_sourcetypes: str = "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns"
    spl_default_earliest: str = "-24h"
    spl_default_latest: str = "now"
    spl_max_result_limit: int = 100
    spl_allowed_commands: str = (
        "search,stats,where,table,fields,sort,dedup,rename,eval,timechart,bin,bucket,head,streamstats,iplocation,mvexpand"
    )
    spl_blocked_commands: str = "delete,collect,outputlookup,sendemail,script,map,rest,loadjob,inputlookup"
    spl_allowed_lookups: str = ""
    spl_allow_join_in_governed_templates: bool = False
    spl_allow_transaction_in_governed_templates: bool = False

    # ``ai_soc_telemetry_sink`` is the AI-SOC product's own telemetry sink
    # selector (not a Splunk product setting). Supported today: ``db`` (writes
    # to Postgres), ``file`` (append-only NDJSON under ``ai_soc_telemetry_file_dir``
    # for air-gapped deployments without Postgres), and ``none`` (disables
    # telemetry). ``splunk`` and ``both`` are planned and will fail fast at
    # startup until the Splunk telemetry connector is implemented.
    ai_soc_telemetry_sink: str = "db"
    # Directory for the ``file`` telemetry sink. One NDJSON file per UTC day.
    ai_soc_telemetry_file_dir: str = "telemetry_logs"

    app_auth_enabled: bool = True
    app_auth_user: str = "analyst"
    app_auth_password: str = ""
    app_auth_session_secret: str = ""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")


def t4_timeout_matches_code_default(timeout_seconds: float) -> bool:
    """True when the value is the Settings field default (currently 2.0s)."""
    default = float(Settings.model_fields["ai_soc_t4_semantic_understanding_timeout_seconds"].default)
    return float(timeout_seconds) == default


def coe_t4_missing_explicit_timeout(s: Settings) -> bool:
    """COE + T4-on still sitting on the code-default timeout (not operator-supplied)."""
    return (
        s.ai_soc_env_profile.strip().lower() == "coe"
        and bool(s.ai_soc_t4_semantic_understanding_enabled)
        and t4_timeout_matches_code_default(s.ai_soc_t4_semantic_understanding_timeout_seconds)
    )


def _validate(s: Settings) -> Settings:
    routing_mode = s.routing_mode.strip().lower()
    if routing_mode == "llm_primary":
        routing_mode = "llm_assisted_semantic"
        s.routing_mode = routing_mode
    sink = s.ai_soc_telemetry_sink.strip().lower()
    if sink in PLANNED_TELEMETRY_SINKS:
        raise ConfigError(
            f"AI_SOC_TELEMETRY_SINK={sink!r} is reserved for a future Splunk "
            "telemetry connector and is not implemented yet. "
            f"Use one of: {SUPPORTED_TELEMETRY_SINKS}."
        )
    if sink not in SUPPORTED_TELEMETRY_SINKS:
        raise ConfigError(
            f"AI_SOC_TELEMETRY_SINK={sink!r} is not a valid value. "
            f"Use one of: {SUPPORTED_TELEMETRY_SINKS}."
        )
    if s.ai_soc_environment_mode not in {"coe", "customer_test", "production", "air_gapped"}:
        raise ConfigError("AI_SOC_ENVIRONMENT_MODE must be one of: coe, customer_test, production, air_gapped.")
    if s.splunk_mcp_discovery_mode not in {"dynamic", "restricted", "static_only"}:
        raise ConfigError("SPLUNK_MCP_DISCOVERY_MODE must be one of: dynamic, restricted, static_only.")
    if s.splunk_ai_assistant_mode not in {"auto", "enabled", "disabled"}:
        raise ConfigError("SPLUNK_AI_ASSISTANT_MODE must be one of: auto, enabled, disabled.")
    if s.ai_soc_llm_mode.strip().lower() not in SUPPORTED_AI_SOC_LLM_MODES:
        raise ConfigError(
            f"AI_SOC_LLM_MODE={s.ai_soc_llm_mode!r} is not valid. "
            f"Use one of: {SUPPORTED_AI_SOC_LLM_MODES}."
        )
    if routing_mode not in SUPPORTED_ROUTING_MODES:
        raise ConfigError(
            f"ROUTING_MODE={s.routing_mode!r} is not valid. "
            f"Use one of: {SUPPORTED_ROUTING_MODES}."
        )
    if routing_mode == "llm_primary_lab":
        if s.ai_soc_environment_mode == "production" or not s.routing_lab_llm_primary_enabled:
            raise ConfigError("ROUTING_MODE=llm_primary_lab requires non-production mode and ROUTING_LAB_LLM_PRIMARY_ENABLED=true.")
    shadow_provider = s.demo_llm_shadow_provider.strip().lower()
    if shadow_provider not in {"disabled", "fake", "huggingface"}:
        raise ConfigError(
            "DEMO_LLM_SHADOW_PROVIDER must be one of: disabled, fake, huggingface."
        )
    from app.routing.route_authority_allowlist import (
        parse_route_authority_coverage_allowlist,
        validate_allowlist_ids,
    )

    allowlist = parse_route_authority_coverage_allowlist(s.route_authority_operation_coverage_allowlist)
    if allowlist:
        try:
            validate_allowlist_ids(allowlist)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    parse_cors_allowed_origins(s.ai_soc_cors_allowed_origins)
    from app.chat.planning_telemetry_policy import validate_canonical_planning_telemetry_config

    validate_canonical_planning_telemetry_config(s)
    retired_flow_check = (
        s.ai_soc_flow_check_mode.strip()
        or os.environ.get("AI_SOC_FLOW_CHECK_MODE", "").strip()
    )
    if retired_flow_check:
        logging.getLogger("ai_soc.config").warning(
            "retired_env_key_ignored",
            extra={"key": "AI_SOC_FLOW_CHECK_MODE", "value": retired_flow_check},
        )
    if coe_t4_missing_explicit_timeout(s):
        raise ConfigError(
            "COE profile with T4 enabled requires an explicit "
            "AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS override in .env. "
            "The code default 2.0s is not a COE qualification value. "
            "Do not copy the VPS 120s bound as a COE SLO; measure on COE."
        )
    return s


settings = _validate(Settings())
