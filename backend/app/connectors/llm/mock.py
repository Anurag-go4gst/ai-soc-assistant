from __future__ import annotations

from typing import Any

from app.connectors.llm.base import SkillRoutingCompletion, SynthesisCompletion
from app.connectors.mcp.base import ConnectorStatus


class MockLlmConnector:
    mode = "mock"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(mode=self.mode, configured=True, available=True, detail="mock")

    def complete_skill_routing(self, payload: dict[str, Any]) -> SkillRoutingCompletion:
        query = str(payload.get("query") or payload.get("user_query") or "").lower()
        if "spl" in query:
            skill = "spl_generation"
        elif (
            "attack" in query
            or "failed" in query
            or "failure" in query
            or "brute" in query
            or "successful login" in query
            or "successful logins" in query
            or "unusual source" in query
            or "new source" in query
            or "abnormally high" in query
        ):
            skill = "attack_discovery"
        elif "alert" in query or "lockout" in query or "lockouts" in query or "locked" in query:
            skill = "alert_summary"
        else:
            skill = "knowledge_recall"
        return SkillRoutingCompletion(
            skill=skill,
            confidence=0.72,
            rationale="deterministic_mock_keyword_route",
            metadata={"mock": True},
        )

    def complete_synthesis(self, payload: dict[str, Any]) -> SynthesisCompletion:
        evidence_refs = [str(ref) for ref in payload.get("evidence_refs", [])][:5]
        if not evidence_refs and not payload.get("summary"):
            return SynthesisCompletion(
                answer="Insufficient evidence.",
                confidence=0.0,
                insufficient_evidence=True,
                metadata={"mock": True},
            )
        return SynthesisCompletion(
            answer=str(payload.get("summary") or "Mock synthesis based on bounded approved evidence."),
            confidence=0.68,
            evidence_refs=evidence_refs,
            metadata={"mock": True},
        )
