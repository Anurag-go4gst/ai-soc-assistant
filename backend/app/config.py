from pydantic_settings import BaseSettings, SettingsConfigDict


# Telemetry sink values that are wired up today. ``splunk`` and ``both`` are
# reserved for a future Splunk telemetry connector; until that connector
# lands the config layer rejects them at startup (see ``_validate``).
SUPPORTED_TELEMETRY_SINKS: tuple[str, ...] = ("db", "none")
PLANNED_TELEMETRY_SINKS: tuple[str, ...] = ("splunk", "both")


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

    splunk_mcp_enabled: bool = False
    splunk_mcp_base_url: str = ""
    splunk_mcp_token: str = ""
    llm_enabled: bool = False
    foundation_sec_instruct_url: str = ""
    foundation_sec_reasoning_url: str = ""
    reasoning_enabled: bool = False
    routing_mode: str = "llm_primary"
    debug_trace_enabled: bool = True
    routing_deterministic_threshold: float = 0.70
    routing_llm_shadow_enabled: bool = True
    routing_compare_logging_enabled: bool = True
    mcp_mode: str = "mock"
    mcp_servers: str = ""
    mcp_default_server: str = "splunk_soc"
    mcp_global_execution_enabled: bool = False
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
    embeddings_mode: str = "mock"
    telemetry_mode: str = "db"
    spl_validation_enabled: bool = True
    spl_allowed_indexes: str = "pgcil_soc"
    spl_allowed_sourcetypes: str = "pgcil:auth"
    spl_default_earliest: str = "-24h"
    spl_default_latest: str = "now"
    spl_max_result_limit: int = 100
    spl_allowed_commands: str = "search,stats,where,table,fields,sort,dedup,rename,eval,timechart,bin,head"
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
    return s


settings = _validate(Settings())
