from __future__ import annotations

from typing import Protocol

from app.connectors.mcp.base import ConnectorStatus


class EmbeddingsConnector(Protocol):
    def health(self) -> ConnectorStatus:
        ...

    def embed_text(self, text: str) -> list[float]:
        ...
