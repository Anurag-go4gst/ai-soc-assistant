"""OPTIONAL_PHASE_S S8a — deterministic optimization provenance."""

from __future__ import annotations

from app.spl.spl_auto_fix_safe import apply_auto_fix_safe
from app.spl.spl_provenance_trace import (
    build_deterministic_optimization_trace,
    build_optimization_analyst_summary,
    should_surface_optimization_advisory,
)


def test_compiler_trace_fields() -> None:
    trace = build_deterministic_optimization_trace(
        optimization_source="compiler",
        candidate_version="v2",
        rules_triggered=["SOC-STD-SPL-001-Q18"],
        rules_resolved=["early_projection"],
        rewrite_guard={"verdict": "PASS"},
        validator={"approved": False},
        llm_lineage=False,
        producer_lineage="llm_plan_compiler",
    )
    assert trace["optimization_source"] == "compiler"
    assert trace["candidate_version"] == "v2"
    assert trace["llm_lineage"] is False
    assert trace["rewrite_guard"]["verdict"] == "PASS"


def test_rewrite_trace_sticky_lineage() -> None:
    trace = build_deterministic_optimization_trace(
        optimization_source="deterministic_rewrite",
        candidate_version="v2",
        llm_lineage=True,
    )
    assert trace["llm_lineage"] is True


def test_analyst_summary_capped_and_plain() -> None:
    lines = build_optimization_analyst_summary(
        optimization_source="deterministic_rewrite",
        steps=["or_chain_to_in"],
    )
    assert len(lines) <= 3
    assert all("model" not in line.lower() for line in lines)
    assert all("llm" not in line.lower() for line in lines)


def test_advisory_absent_on_normal_turn() -> None:
    assert should_surface_optimization_advisory(explicit_optimize_intent=False) is False
    summary = build_optimization_analyst_summary(
        optimization_source="deterministic_rewrite",
        steps=["or_chain_to_in"],
        explicit_optimize_intent=False,
    )
    assert summary == []


def test_advisory_present_on_explicit_optimize() -> None:
    assert should_surface_optimization_advisory(explicit_optimize_intent=True) is True
    summary = build_optimization_analyst_summary(
        optimization_source="deterministic_rewrite",
        steps=[],
        explicit_optimize_intent=True,
    )
    assert summary


def test_auto_fix_wires_provenance_shape() -> None:
    arms = " OR ".join(f"EventCode={4624 + i}" for i in range(10))
    spl = f"search index=auth sourcetype=linux earliest=-1h latest=now {arms} | stats count | head 100"
    fix = apply_auto_fix_safe(spl, llm_lineage=True)
    trace = build_deterministic_optimization_trace(
        optimization_source="deterministic_rewrite",
        candidate_version="v2" if fix.applied else "v1",
        rules_triggered=["SOC-STD-SPL-001-Q04"],
        rules_resolved=fix.steps,
        rewrite_guard=fix.rewrite_guard,
        llm_lineage=fix.llm_lineage,
    )
    assert trace["optimization_source"] == "deterministic_rewrite"
    assert trace["llm_lineage"] is True
