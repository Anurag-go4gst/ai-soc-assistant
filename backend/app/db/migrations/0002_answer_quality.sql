CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_turns (
    turn_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    entrypoint TEXT,
    user_query TEXT NOT NULL,
    normalized_query TEXT NOT NULL,
    selected_skill TEXT,
    selected_use_case_id TEXT,
    question_ref TEXT,
    answer_mode TEXT,
    response_mode TEXT,
    final_message TEXT,
    analyst_summary TEXT,
    analyst_response JSONB NOT NULL DEFAULT '{}'::jsonb,
    candidate_spl TEXT,
    spl_validation JSONB NOT NULL DEFAULT '{}'::jsonb,
    mitre_decision JSONB NOT NULL DEFAULT '{}'::jsonb,
    mitre_mappings JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    control_plane_trace JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_status TEXT,
    llm_used BOOLEAN NOT NULL DEFAULT false,
    rag_used BOOLEAN NOT NULL DEFAULT false,
    mcp_used BOOLEAN NOT NULL DEFAULT false,
    quality_status TEXT NOT NULL DEFAULT 'unreviewed',
    golden_candidate BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_answer_feedback (
    feedback_id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    trace_id TEXT,
    user_id TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('up', 'down', 'neutral')),
    remark TEXT CHECK (remark IS NULL OR char_length(remark) <= 2000),
    category TEXT,
    review_status TEXT NOT NULL DEFAULT 'new',
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (turn_id, user_id)
);

CREATE TABLE IF NOT EXISTS answer_quality_reviews (
    review_id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    review_notes TEXT,
    recommended_action TEXT,
    linked_issue TEXT,
    linked_pr TEXT,
    golden_case_id TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_turns_trace_id ON chat_turns(trace_id);
CREATE INDEX IF NOT EXISTS idx_chat_turns_quality_status ON chat_turns(quality_status);
CREATE INDEX IF NOT EXISTS idx_chat_turns_question_ref ON chat_turns(question_ref);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_turn_id ON chat_answer_feedback(turn_id);
CREATE INDEX IF NOT EXISTS idx_answer_quality_reviews_turn_id ON answer_quality_reviews(turn_id);

INSERT INTO schema_migrations (version) VALUES ('0002_answer_quality')
ON CONFLICT (version) DO NOTHING;
