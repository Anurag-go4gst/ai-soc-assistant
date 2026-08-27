"""OPTIONAL_PHASE_S — orchestrate Layer 2 + Layer 3 on a lab-tier candidate (sticky lineage)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.spl.draft_quality import evaluate_draft_quality
from app.spl.spl_auto_fix_safe import apply_auto_fix_safe
from app.spl.spl_optimization_llm import OptimizationLlmResult, apply_optimization_llm
from app.spl.spl_provenance_trace import build_deterministic_optimization_trace


@dataclass
class SplOptimizationChainResult:
    candidate_spl: str
    candidate_version: str = "v1"
    llm_lineage: bool = True
    optimization_trace: dict[str, Any] = field(default_factory=dict)
    optimization_llm: OptimizationLlmResult | None = None


def run_spl_optimization_chain(
    candidate_spl: str,
    *,
    llm_lineage: bool = True,
    user_query: str | None = None,
    rqc: dict[str, Any] | None = None,
    intent_spec: dict[str, Any] | None = None,
) -> SplOptimizationChainResult:
    """Layer 2 deterministic rewrite then optional Layer 3 bounded LLM (one call max)."""
    current = (candidate_spl or "").strip()
    trace_steps: list[str] = []
    rules_triggered: list[str] = []
    rules_resolved: list[str] = []
    optimization_source = "generation_prompt"

    quality = evaluate_draft_quality(current)
    rules_triggered = [f.rule_id for f in quality.findings if f.severity == "advisory"]

    fix = apply_auto_fix_safe(
        current,
        rqc=rqc,
        intent_spec=intent_spec,
        llm_lineage=llm_lineage,
    )
    if fix.applied:
        current = fix.candidate_spl
        trace_steps.extend(fix.steps)
        rules_resolved.extend(fix.steps)
        optimization_source = "deterministic_rewrite"

    quality = evaluate_draft_quality(current)
    opt: OptimizationLlmResult | None = None
    if settings.ai_soc_spl_optimization_llm_enabled:
        opt = apply_optimization_llm(
            current,
            classification=quality.optimization_classification,
            advisory_rules=rules_triggered,
            user_query=user_query,
            rqc=rqc,
            llm_lineage=llm_lineage,
        )
        if opt.outcome == "OPTIMIZED" and opt.candidate_spl_v2:
            current = opt.candidate_spl_v2
            optimization_source = "optimization_llm"
            trace_steps.append("optimization_llm_v2")

    version = "v2" if trace_steps else "v1"
    opt_trace = build_deterministic_optimization_trace(
        optimization_source=optimization_source,  # type: ignore[arg-type]
        candidate_version=version,
        rules_triggered=rules_triggered,
        rules_resolved=rules_resolved or trace_steps,
        rewrite_guard=fix.rewrite_guard if fix.applied else {},
        llm_lineage=llm_lineage,
        producer_lineage="optimization_llm" if optimization_source == "optimization_llm" else None,
    )
    if opt is not None:
        opt_trace["optimization_llm"] = {
            "outcome": opt.outcome,
            "model": opt.model,
            "latency_ms": opt.latency_ms,
            "skip_reason": opt.skip_reason,
        }

    return SplOptimizationChainResult(
        candidate_spl=current,
        candidate_version=version,
        llm_lineage=llm_lineage,
        optimization_trace=opt_trace,
        optimization_llm=opt,
    )


def resolve_producer_lineage(candidate: dict[str, Any] | None) -> str:
    """Sticky producer label for llm_derived_spl_artifact (P11 fix)."""
    if not isinstance(candidate, dict):
        return "llm_plan_compiler"
    explicit = str(candidate.get("producer_lineage") or "").strip()
    if explicit:
        return explicit
    provider = str(candidate.get("selected_candidate_spl_provider") or "").strip()
    if provider == "llm_spl_advisory_fallback":
        if candidate.get("spl_plan_compiler_telemetry", {}).get("role") == "spl_plan_compiler":
            return "llm_plan_compiler"
        return "llm_fallback"
    if provider:
        return provider
    mode = str(candidate.get("generation_mode") or "").strip()
    if "plan" in mode:
        return "llm_plan_compiler"
    if "fallback" in mode or "advisory" in mode:
        return "llm_fallback"
    return "llm_plan_compiler"
