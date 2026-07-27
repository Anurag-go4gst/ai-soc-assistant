-- Canonical retention purge indexes (item 28). Additive only — do not edit 0004/0005.

CREATE INDEX IF NOT EXISTS canonical_handoffs_expires_at_status_idx
    ON canonical_handoffs (expires_at, status);

CREATE INDEX IF NOT EXISTS canonical_planning_events_created_at_event_idx
    ON canonical_planning_events (created_at, event);

INSERT INTO schema_migrations (version)
VALUES ('0006_canonical_retention_indexes')
ON CONFLICT (version) DO NOTHING;
