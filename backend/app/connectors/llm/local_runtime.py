from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.llm.base import SkillRoutingCompletion, SynthesisCompletion
from app.connectors.llm.mock import MockLlmConnector
from app.connectors.mcp.base import ConnectorStatus


class LocalRuntimeLlmConnector:
    mode = "local_runtime"

    def health(self) -> ConnectorStatus:
        configured = bool(settings.foundation_sec_instruct_url.strip())
        return ConnectorStatus(
            mode=self.mode,
            configured=configured,
            available=False,
            detail="placeholder_not_implemented",
        )

    def complete_skill_routing(self, payload: dict[str, Any]) -> SkillRoutingCompletion:
        return MockLlmConnector().complete_skill_routing(payload)

    def complete_synthesis(self, payload: dict[str, Any]) -> SynthesisCompletion:
        return MockLlmConnector().complete_synthesis(payload)
