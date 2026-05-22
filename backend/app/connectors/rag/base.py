from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.connectors.mcp.base import ConnectorStatus


@dataclass(frozen=True)
class RagChunk:
    doc_id: str
    title: str
    chunk_id: str
    score: float
    source_type: str
    approved: bool
    excerpt: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RagConnector(Protocol):
    def health(self) -> ConnectorStatus:
        ...

    def retrieve(self, query: str, filters: dict[str, Any] | None = None) -> list[RagChunk]:
        ...
