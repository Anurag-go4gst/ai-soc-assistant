-- Schema for a future durable MCP discovery snapshot store, mirroring the
-- in-memory store at app/connectors/mcp/discovery_snapshot.py. Not yet
-- wired to a writer/reader connector -- this migration only reserves the
-- table shape so a Postgres-backed store can be added without a schema
-- change later. Never stores tokens/credentials/raw evidence -- tools_json
-- holds only redacted discovery metadata (name/description/inputSchema/
-- annotations), the same shape as DiscoverySnapshot.to_safe_dict().
CREATE TABLE IF NOT EXISTS mcp_discovery_snapshot (
    id BIGSERIAL PRIMARY KEY,
    server_name TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    error_reason TEXT,
    tools_json JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_mcp_discovery_snapshot_server_captured
    ON mcp_discovery_snapshot (server_name, captured_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('0007_mcp_discovery_snapshot')
ON CONFLICT (version) DO NOTHING;
