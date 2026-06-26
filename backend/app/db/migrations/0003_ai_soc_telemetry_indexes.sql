CREATE INDEX IF NOT EXISTS idx_ai_trace_runs_started_at ON ai_trace_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_trace_runs_entrypoint_status ON ai_trace_runs (entrypoint, status);

INSERT INTO schema_migrations (version) VALUES ('0003_ai_soc_telemetry_indexes')
ON CONFLICT (version) DO NOTHING;
