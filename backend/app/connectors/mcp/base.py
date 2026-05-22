from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ConnectorStatus:
    mode: str
    configured: bool
    available: bool
    detail: str = "ok"


@dataclass(frozen=True)
class ValidatedSplRequest:
    spl: str
    earliest_time: str | None = None
    latest_time: str | None = None
    max_rows: int = 1000
    validation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeObjectRequest:
    object_type: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)


class McpConnector(Protocol):
    def health(self) -> ConnectorStatus:
        ...

    def execute_validated_spl(self, request: ValidatedSplRequest) -> dict[str, Any]:
        ...

    def discover_knowledge_objects(self, request: KnowledgeObjectRequest) -> dict[str, Any]:
        ...
