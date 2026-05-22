from __future__ import annotations

from typing import Any

from app.connectors.mcp.base import ConnectorStatus
from app.connectors.rag.base import RagChunk
from app.connectors.rag.mock import MockRagConnector


class LocalVectorRagConnector:
    mode = "local_vector"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(
            mode=self.mode,
            configured=False,
            available=False,
            detail="placeholder_not_implemented",
            implemented=False,
            fallback="mock",
        )

    def retrieve(self, query: str, filters: dict[str, Any] | None = None) -> list[RagChunk]:
        return MockRagConnector().retrieve(query, filters)
