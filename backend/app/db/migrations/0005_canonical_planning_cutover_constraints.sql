-- Canonical planning cutover constraints (item 18). Additive only — do not edit 0004.

-- Clarification resumption lookups.
CREATE INDEX IF NOT EXISTS canonical_handoffs_awaiting_clarification_idx
    ON canonical_handoffs (handoff_id, handoff_version)
    WHERE status = 'awaiting_clarification';

CREATE INDEX IF NOT EXISTS canonical_handoffs_session_awaiting_idx
    ON canonical_handoffs (session_id, handoff_id, handoff_version)
    WHERE status = 'awaiting_clarification';

-- Planning-event deduplication by decision id (audit spine).
CREATE UNIQUE INDEX IF NOT EXISTS canonical_planning_events_decision_dedup_idx
    ON canonical_planning_events (decision_id)
    WHERE decision_id IS NOT NULL;

-- Execution idempotency lease support (item 20 prep).
ALTER TABLE canonical_execution_idempotency
    ADD COLUMN IF NOT EXISTS lease_owner TEXT,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS operation TEXT,
    ADD COLUMN IF NOT EXISTS operation_contract TEXT,
    ADD COLUMN IF NOT EXISTS downstream_idempotency_key TEXT;

CREATE INDEX IF NOT EXISTS canonical_execution_idempotency_lease_idx
    ON canonical_execution_idempotency (lease_expires_at)
    WHERE lease_expires_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS canonical_execution_idempotency_downstream_key_idx
    ON canonical_execution_idempotency (downstream_idempotency_key)
    WHERE downstream_idempotency_key IS NOT NULL;

INSERT INTO schema_migrations (version)
VALUES ('0005_canonical_planning_cutover_constraints')
ON CONFLICT (version) DO NOTHING;
