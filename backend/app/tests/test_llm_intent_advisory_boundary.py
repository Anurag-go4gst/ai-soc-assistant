from __future__ import annotations

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.pipeline import graph_node_query_to_intent
from app.config import settings
from app.query_understanding.models import (
    OutputTemplate,
    QueryEntities,
    QueryUnderstandingResult,
    RequestedOutputType,
)
from app.schemas.requests import ChatRequest


def test_query_to_intent_keeps_typed_advisory_for_live_consumers(monkeypatch) -> None:
    advisory = LLMIntentAdvisory(
        llm_called=True,
        evidence_need_hints=["vpn_auth", "ot_jump_host"],
        confidence_metadata={"score": 0.73},
        provider_label="test-provider",
    )
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.generate_llm_intent_advisory", lambda *args, **kwargs: advisory)

    understanding = QueryUnderstandingResult(
        raw_query="Correlate vendor VPN and OT jump-host access",
        normalized_query="correlate vendor vpn and ot jump-host access",
        primary_intent="investigate",
        requested_output_type=RequestedOutputType.INVESTIGATION,
        output_template=OutputTemplate.INVESTIGATION_ANSWER,
        entities=QueryEntities(),
        confidence=0.4,
        deterministic_match_path="out_of_registry",
        soc_investigation_shaped=True,
    )
    state = {
        "request": ChatRequest(message=understanding.raw_query),
        "effective_query": understanding.raw_query,
        "query_understanding": understanding,
        "routed": {"skill": "guided_investigation"},
    }

    result = graph_node_query_to_intent(state)

    assert isinstance(result["llm_intent_advisory"], LLMIntentAdvisory)
    assert result["llm_intent_advisory"].evidence_need_hints == ["vpn_auth", "ot_jump_host"]
    assert result["query_to_intent"]["llm_intent_advisory"]["provider_label"] == "test-provider"
