from __future__ import annotations

from typing import Any

from app.connectors.llm.base import SkillRoutingCompletion, SynthesisCompletion
from app.connectors.llm.mock import MockLlmConnector
from app.connectors.mcp.base import ConnectorStatus


class DevTeacherLlmConnector:
    mode = "dev_teacher"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(
            mode=self.mode,
            configured=False,
            available=False,
            detail="placeholder_not_implemented",
            implemented=False,
            fallback="mock",
        )

    def complete_skill_routing(self, payload: dict[str, Any]) -> SkillRoutingCompletion:
        return MockLlmConnector().complete_skill_routing(payload)

    def complete_synthesis(self, payload: dict[str, Any]) -> SynthesisCompletion:
        return MockLlmConnector().complete_synthesis(payload)
