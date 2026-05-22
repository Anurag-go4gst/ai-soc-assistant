from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.connectors.mcp.base import ConnectorStatus


@dataclass(frozen=True)
class SkillRoutingCompletion:
    skill: str
    confidence: float
    rationale: str
    insufficient_evidence: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SynthesisCompletion:
    answer: str
    confidence: float
    evidence_refs: list[str] = field(default_factory=list)
    insufficient_evidence: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class LlmConnector(Protocol):
    def health(self) -> ConnectorStatus:
        ...

    def complete_skill_routing(self, payload: dict[str, Any]) -> SkillRoutingCompletion:
        ...

    def complete_synthesis(self, payload: dict[str, Any]) -> SynthesisCompletion:
        ...
