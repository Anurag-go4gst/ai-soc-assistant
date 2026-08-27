"""OPTIONAL_PHASE_S S8b — LLM-path provenance."""

from __future__ import annotations

from app.spl.spl_provenance_trace import build_llm_path_optimization_trace


def test_llm_path_trace_includes_generation_and_optimization_llm() -> None:
    trace = build_llm_path_optimization_trace(
        optimization_source="generation_prompt",
        candidate_version="v1",
        producer_lineage="llm_fallback",
        generation_prompt_efficiency=True,
        optimization_llm={"outcome": "NO_SAFE_OPTIMIZATION", "latency_ms": 42},
        rules_triggered=["Q03"],
        llm_lineage=True,
    )
    assert trace["optimization_source"] == "generation_prompt"
    assert trace["producer_lineage"] == "llm_fallback"
    assert trace["generation_prompt_efficiency"] is True
    assert trace["llm_lineage"] is True
    assert trace["optimization_llm"]["outcome"] == "NO_SAFE_OPTIMIZATION"
