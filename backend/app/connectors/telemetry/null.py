from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.connectors.mcp.base import ConnectorStatus
from app.connectors.telemetry.base import TraceHandle


class NullTelemetryConnector:
    mode = "none"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(mode=self.mode, configured=True, available=True, detail="no_op")

    def start_trace(self, trace_id: str | None = None, **fields: Any) -> TraceHandle:
        return TraceHandle(trace_id=trace_id or str(uuid4()), metadata={"no_op": True})

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        return None

    def record_routing_decision(self, trace_id: str, **fields: Any) -> None:
        return None

    def record_routing_disagreement(self, trace_id: str, **fields: Any) -> None:
        return None

    def record_spl_validation(self, trace_id: str, **fields: Any) -> None:
        return None

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        return None

    def record_rag_retrieval(self, trace_id: str, **fields: Any) -> None:
        return None

    def record_llm_call(self, trace_id: str, **fields: Any) -> None:
        return None

    def record_harness_result(self, trace_id: str, **fields: Any) -> str:
        return fields.get("test_run_id") or trace_id

    def end_trace(self, trace_id: str, status: str = "completed", **fields: Any) -> None:
        return None
