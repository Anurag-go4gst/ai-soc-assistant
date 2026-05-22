from __future__ import annotations

from typing import Any

from app.connectors.mcp.base import ConnectorStatus
from app.connectors.rag.base import RagChunk


class MockRagConnector:
    mode = "mock"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(mode=self.mode, configured=True, available=True, detail="mock")

    def retrieve(self, query: str, filters: dict[str, Any] | None = None) -> list[RagChunk]:
        return [
            RagChunk(
                doc_id="mock-runbook-auth-001",
                title="Approved Authentication Triage Runbook",
                chunk_id="auth-001:0001",
                score=0.91,
                source_type="runbook",
                approved=True,
                excerpt="Use validated SPL against approved auth indexes and summarize only bounded evidence.",
                metadata={"query_hash": _stable_hash(query), "filters": filters or {}},
            )
        ]


def _stable_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
