from __future__ import annotations

from app.connectors.embeddings.mock import MockEmbeddingsConnector
from app.connectors.mcp.base import ConnectorStatus


class LocalEmbeddingsConnector:
    mode = "local"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(
            mode=self.mode,
            configured=False,
            available=False,
            detail="placeholder_not_implemented",
            implemented=False,
            fallback="mock",
        )

    def embed_text(self, text: str) -> list[float]:
        return MockEmbeddingsConnector().embed_text(text)
