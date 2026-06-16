from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.connectors.mcp.base import ConnectorStatus


@dataclass(frozen=True)
class TraceHandle:
    trace_id: str
    run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TelemetryConnector(Protocol):
    def health(self) -> ConnectorStatus:
        ...

    def start_trace(self, trace_id: str | None = None, **fields: Any) -> TraceHandle:
        ...

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        ...

    def record_routing_decision(self, trace_id: str, **fields: Any) -> None:
        ...

    def record_routing_disagreement(self, trace_id: str, **fields: Any) -> None:
        ...

    def record_spl_validation(self, trace_id: str, **fields: Any) -> None:
        ...

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        ...

    def record_rag_retrieval(self, trace_id: str, **fields: Any) -> None:
        ...

    def record_llm_call(self, trace_id: str, **fields: Any) -> None:
        ...

    def record_harness_result(self, trace_id: str, **fields: Any) -> str:
        ...

    def end_trace(self, trace_id: str, status: str = "completed", **fields: Any) -> None:
        ...

    def merge_run_metadata(self, trace_id: str, metadata: dict[str, Any]) -> None:
        ...
