-- Canonical handoff persistence and planning telemetry (durable).

CREATE TABLE IF NOT EXISTS canonical_handoffs (
    id BIGSERIAL PRIMARY KEY,
    handoff_id TEXT NOT NULL,
    handoff_version INTEGER NOT NULL,
    session_id TEXT,
    turn_id TEXT,
    trace_id TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    original_query TEXT,
    original_skill TEXT,
    original_use_case_id TEXT,
    original_answer_goal TEXT,
    initial_tier TEXT,
    resolved_tier TEXT,
    canonical_planning_input JSONB,
    gap_resolution JSONB,
    unresolved_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    clarification_reason TEXT,
    committed_resource_plan_id TEXT,
    committed_resource_plan JSONB,
    committed_evidence_plan JSONB,
    duplicate_call_hashes JSONB NOT NULL DEFAULT '[]'::jsonb,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '60 minutes'),
    CONSTRAINT canonical_handoffs_handoff_version_unique UNIQUE (handoff_id, handoff_version)
);

CREATE UNIQUE INDEX IF NOT EXISTS canonical_handoffs_committed_plan_unique
    ON canonical_handoffs (handoff_id, handoff_version)
    WHERE status = 'plan_committed' AND committed_resource_plan_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS canonical_handoffs_session_status_idx
    ON canonical_handoffs (session_id, status);

CREATE INDEX IF NOT EXISTS canonical_handoffs_trace_idx
    ON canonical_handoffs (trace_id);

CREATE TABLE IF NOT EXISTS canonical_planning_events (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT,
    turn_id TEXT,
    session_id TEXT,
    decision_id TEXT,
    parent_decision_id TEXT,
    handoff_id TEXT,
    handoff_version INTEGER,
    resource_plan_id TEXT,
    event TEXT NOT NULL,
    node_name TEXT,
    node_version TEXT,
    contract_version TEXT,
    status TEXT,
    duration_ms INTEGER,
    error_category TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS canonical_planning_events_trace_idx
    ON canonical_planning_events (trace_id, created_at);

CREATE INDEX IF NOT EXISTS canonical_planning_events_handoff_idx
    ON canonical_planning_events (handoff_id, handoff_version);

CREATE TABLE IF NOT EXISTS canonical_execution_idempotency (
    id BIGSERIAL PRIMARY KEY,
    resource_plan_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    handoff_id TEXT,
    handoff_version INTEGER,
    status TEXT NOT NULL DEFAULT 'started',
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT canonical_execution_idempotency_key_unique UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS canonical_execution_idempotency_plan_step_idx
    ON canonical_execution_idempotency (resource_plan_id, step_id);

INSERT INTO schema_migrations (version)
VALUES ('0004_canonical_handoffs')
ON CONFLICT (version) DO NOTHING;
