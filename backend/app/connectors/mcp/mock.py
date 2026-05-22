from __future__ import annotations

from typing import Any

from app.connectors.mcp.base import ConnectorStatus, KnowledgeObjectRequest, ValidatedSplRequest


class MockMcpConnector:
    mode = "mock"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(mode=self.mode, configured=True, available=True, detail="mock")

    def execute_validated_spl(self, request: ValidatedSplRequest) -> dict[str, Any]:
        return {
            "status": "ok",
            "mock": True,
            "spl_hash": _stable_hash(request.spl),
            "row_count": 1,
            "rows": [{"result": "mock_spl_execution", "spl_hash": _stable_hash(request.spl)}],
        }

    def discover_knowledge_objects(self, request: KnowledgeObjectRequest) -> dict[str, Any]:
        return {
            "status": "ok",
            "mock": True,
            "objects": [
                {
                    "name": "pgcil_auth_summary",
                    "object_type": request.object_type or "savedsearch",
                    "approved": True,
                }
            ],
        }


def _stable_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
