from pydantic_settings import BaseSettings, SettingsConfigDict


# Telemetry sink values that are wired up today. ``splunk`` and ``both`` are
# reserved for a future Splunk telemetry connector; until that connector
# lands the config layer rejects them at startup (see ``_validate``).
SUPPORTED_TELEMETRY_SINKS: tuple[str, ...] = ("db", "none")
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


class Settings(BaseSettings):
    app_env: str = "development"
    backend_port: int = 8010
    frontend_port: int = 3010

    # Default matches the Docker Compose `postgres` service hostname and the
    # placeholder password used by `.env.example`. Production deployments
    # MUST override DATABASE_URL via env vars and never rely on this default.
    # This default is intentionally a dev placeholder, never a real secret.
    database_url: str = "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant"

    splunk_mcp_enabled: bool = True
    ai_soc_environment_mode: str = "coe"
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
    splunk_run_query_require_validation: bool = True
    splunk_metadata_discovery_allowed: bool = True
    splunk_knowledge_object_discovery_allowed: bool = True
    splunk_allowed_core_tools: str = "splunk_run_query,splunk_get_info,splunk_get_indexes,splunk_get_index_info,splunk_get_metadata,splunk_get_user_info,splunk_get_knowledge_objects"
    splunk_allowed_saia_tools: str = "saia_generate_spl,saia_explain_spl,saia_optimize_spl,saia_ask_splunk_question"
    splunk_mcp_base_url: str = ""
    splunk_mcp_token: str = ""
    llm_enabled: bool = False
    foundation_sec_instruct_url: str = ""
    foundation_sec_reasoning_url: str = ""
    reasoning_enabled: bool = False
    routing_mode: str = "llm_assisted_semantic"
    routing_lab_llm_primary_enabled: bool = False
    debug_trace_enabled: bool = True
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
    ai_soc_llm_shadow_narration_enabled: bool = False
    ioc_registry_enabled: bool = False
    ioc_registry_path: str = ""
    detection_registry_enabled: bool = False
    detection_registry_path: str = ""
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
    ai_soc_llm_timeout_seconds: int = 30
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
    # Phase 4/5: curated enrichment activation for runtime evidence/planner paths. Default off.
    ai_soc_curated_enrichment_activation_enabled: bool = False
    ai_soc_llm_reasoning_provider: str = ""
    ai_soc_llm_reasoning_model: str = ""
    ai_soc_llm_synthesis_provider: str = ""
    ai_soc_llm_synthesis_model: str = ""
    ai_soc_llm_spl_advisory_provider: str = ""
    ai_soc_llm_spl_advisory_model: str = ""
    ai_soc_llm_spl_fallback_enabled: bool = False
    # Regenerate-once on the SPL failover relevance gate. Default off: one LLM call
    # per failover turn so slow on-prem hardware does not double worst-case latency.
    ai_soc_llm_spl_failover_retry_enabled: bool = False
    # Optional JSON map of placeholder stem -> index/sourcetype value for Phase H0.
    ai_soc_source_profile_map: str = ""
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
    # Evidence-gating governance for the upcoming synthesis stage.
    ai_soc_llm_require_context_sufficiency: bool = True
    ai_soc_llm_require_source_refs: bool = True
    ai_soc_llm_allow_insufficient_evidence_response: bool = False
    # Hard kill-switches. Default false; no synthesis or answer guard exists yet.
    ai_soc_llm_final_synthesis_enabled: bool = False
    ai_soc_llm_answer_guard_enabled: bool = False
    # When true (and final synthesis is on, mode is not mock/disabled, and a
    # local/openai-compatible endpoint is configured), the live-chat synthesis
    # narrates the analyst summary with the real model instead of the
    # deterministic lab draft. Defaults false so the test suite and the
    # Experience Center fixture path never make a live model call.
    ai_soc_llm_live_synthesis_enabled: bool = False

    # Stage 3M-S4: Experience Center demo-only LLM shadow (lineage/trace; no final synthesis).
    demo_llm_shadow_enabled: bool = False
    demo_llm_shadow_provider: str = "disabled"
    demo_llm_shadow_model: str = ""
    demo_llm_shadow_endpoint: str = ""
    demo_llm_shadow_timeout_seconds: int = 5
    # P0-9 documentation/readiness: proposed profile name for COE system-check demos.
    # Empty = unset. Does not orchestrate env vars until a later stage wires it.
    ai_soc_flow_check_mode: str = ""
    # When true, /chat returns the same governed payload as Experience Center when the
    # user message exactly matches a demo scenario query (normalized). Does not enable
    # real Splunk MCP or live Foundation-sec calls.
    ai_soc_live_chat_ec_parity_enabled: bool = False
    # P1: LangGraph orchestration parity with imperative /chat (default off).
    langgraph_orchestration_enabled: bool = False
    # Phase 12: planner-led fan-out/fan-in shadow graph for tests/trace only (default off).
    ai_soc_langgraph_shadow_enabled: bool = False
    # Chat control plane rollout gate. Default false until golden tests pass.
    control_plane_enabled: bool = False
    # Batch 5 — lightweight investigation session pins (structured only, no transcript).
    ai_soc_session_context_enabled: bool = True
    ai_soc_session_context_ttl_minutes: int = 30

    embeddings_mode: str = "mock"
    telemetry_mode: str = "db"
    spl_validation_enabled: bool = True
    spl_allowed_indexes: str = "pgcil_soc"
    spl_allowed_sourcetypes: str = "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns"
    spl_default_earliest: str = "-24h"
    spl_default_latest: str = "now"
    spl_max_result_limit: int = 100
    spl_allowed_commands: str = (
        "search,stats,where,table,fields,sort,dedup,rename,eval,timechart,bin,head,streamstats"
    )
    spl_blocked_commands: str = "delete,collect,outputlookup,sendemail,script,map,rest,loadjob,inputlookup"

    # ``ai_soc_telemetry_sink`` is the AI-SOC product's own telemetry sink
    # selector (not a Splunk product setting). Supported today: ``db`` (writes
    # to Postgres) and ``none`` (disables telemetry). ``splunk`` and ``both``
    # are planned and will fail fast at startup until the Splunk telemetry
    # connector is implemented.
    ai_soc_telemetry_sink: str = "db"

    app_auth_enabled: bool = True
    app_auth_user: str = "analyst"
    app_auth_password: str = ""
    app_auth_session_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


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
    flow_check = s.ai_soc_flow_check_mode.strip().lower()
    if flow_check and flow_check not in SUPPORTED_AI_SOC_FLOW_CHECK_MODES:
        raise ConfigError(
            f"AI_SOC_FLOW_CHECK_MODE={s.ai_soc_flow_check_mode!r} is not valid. "
            f"Use one of: {SUPPORTED_AI_SOC_FLOW_CHECK_MODES}."
        )
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
    return s


settings = _validate(Settings())
