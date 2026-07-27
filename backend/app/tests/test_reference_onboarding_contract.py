from __future__ import annotations

from typing import Any

import pytest

from app.chat.answer_shape_router import classify_answer_shape
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.planner import reference_registry as registry_module
from app.planner.reference_registry import ReferenceDataset, ReferenceFact, ReferenceRegistry, ReferenceResolver
from app.schemas.requests import ChatRequest


QUERY = "Explain TTX-123 in the test taxonomy."


class SyntheticResolver(ReferenceResolver):
    def resolve_ids(self, ids: list[str]) -> list[ReferenceFact]:
        return [
            ReferenceFact(
                reference_id=reference_id,
                dataset_id="test_taxonomy",
                name="Synthetic Technique",
                description="Synthetic reference row used to prove registry-only onboarding.",
                tactics=["TA.TEST"],
                citation="local synthetic taxonomy fixture",
            )
            for reference_id in ids
            if reference_id == "TTX-123"
        ]

    def search_domain(self, keywords: list[str], *, limit: int = 10) -> list[ReferenceFact]:
        if any("test taxonomy" in keyword.lower() for keyword in keywords):
            return self.resolve_ids(["TTX-123"])[:limit]
        return []


@pytest.fixture(autouse=True)
def _offline_reference_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEMETRY_MODE", "none")
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)


@pytest.fixture
def synthetic_reference_registry(monkeypatch: pytest.MonkeyPatch) -> ReferenceRegistry:
    base_registry = registry_module.load_reference_registry()
    synthetic_dataset = ReferenceDataset(
        dataset_id="test_taxonomy",
        id_patterns=(r"TTX-\d{3}",),
        keyword_domains=("test taxonomy", "synthetic technique"),
        resolver=SyntheticResolver(),
        provenance_tier="test_only_registry_entry",
    )
    registry = ReferenceRegistry([*base_registry.datasets, synthetic_dataset])
    monkeypatch.setattr(registry_module, "load_reference_registry", lambda: registry)
    return registry


def test_synthetic_dataset_onboards_through_registry_only(
    synthetic_reference_registry: ReferenceRegistry,
) -> None:
    assert synthetic_reference_registry.match_id("TTX-123").dataset_id == "test_taxonomy"
    assert classify_answer_shape(QUERY).primary_shape == "reference_taxonomy"

    payload = build_live_chat_response(ChatRequest(message=QUERY)).model_dump(mode="json")
    analyst = payload.get("analyst_response") or {}
    facts = [item for item in analyst.get("reference_facts") or [] if isinstance(item, dict)]
    trace = ((payload.get("control_plane_trace") or {}).get("plan_dispatch") or {})

    assert payload.get("selected_skill") == "knowledge_recall"
    assert (payload.get("evidence_plan") or {}).get("required_sources") == ["reference_registry"]
    assert trace.get("dispatch_schedule") == ["prepare_rag_only", "rag_early", "reference_finalize"]
    assert facts and facts[0]["reference_id"] == "TTX-123"
    assert facts[0]["source_dataset"] == "test_taxonomy"
    assert facts[0]["citation"] == "local synthetic taxonomy fixture"
    assert "Synthetic Technique" in str(analyst.get("direct_answer_summary") or "")
    assert (payload.get("candidate_spl") or {}).get("candidate_spl") in {None, ""}
