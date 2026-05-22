CREATE TABLE IF NOT EXISTS ai_trace_runs (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL UNIQUE,
    run_id TEXT,
    user_id TEXT,
    entrypoint TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_trace_steps (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    step_name TEXT,
    status TEXT,
    event JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS routing_decisions (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    event JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS routing_disagreements (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    event JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS spl_validation_results (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    event JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_execution_logs (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    event JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rag_retrieval_logs (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    event JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_call_logs (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    event JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS harness_test_runs (
    id BIGSERIAL PRIMARY KEY,
    test_run_id TEXT NOT NULL UNIQUE,
    trace_id TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS harness_test_case_results (
    id BIGSERIAL PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    trace_id TEXT,
    case_id TEXT NOT NULL,
    user_query TEXT,
    expected_skill TEXT,
    actual_skill TEXT,
    generated_spl_ref TEXT,
    spl_validation_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    mcp_execution_status TEXT,
    expected_findings JSONB NOT NULL DEFAULT '{}'::jsonb,
    actual_findings_summary TEXT,
    layer_results JSONB NOT NULL DEFAULT '{}'::jsonb,
    final_pass BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT,
    user_id TEXT,
    rating TEXT,
    feedback_summary TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_trace_steps_trace_id ON ai_trace_steps(trace_id);
CREATE INDEX IF NOT EXISTS idx_routing_disagreements_trace_id ON routing_disagreements(trace_id);
CREATE INDEX IF NOT EXISTS idx_harness_case_results_run_id ON harness_test_case_results(test_run_id);
