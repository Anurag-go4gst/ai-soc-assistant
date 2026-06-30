from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.chat.contracts.slot_handoff import SlotHandoffSummary


class PipelineStage(str, Enum):
    """Ordered execution stages — the sole routing surface (Phase 2B+)."""

    rag_early = "rag_early"
    pre_spl_mcp_discovery = "pre_spl_mcp_discovery"
    workflow_spl = "workflow_spl"
    spl_postprocessor = "spl_postprocessor"
    spl_source_resolve = "spl_source_resolve"
    mcp_execution = "mcp_execution"
    mitre_finalize = "mitre_finalize"
    cve_adapter = "cve_adapter"


class LlmHop(str, Enum):
    """Post-evidence LLM hops only — 2C is excluded (see IntentDispatchDecision)."""

    mcp_tool_planner = "mcp_tool_planner"
    spl_plan_compiler = "spl_plan_compiler"
    narration = "narration"


RequestMode = Literal[
    "spl_authoring",
    "spl_and_run",
    "live_investigation",
    "knowledge",
    "mitre_knowledge",
    "cve_review",
    "hybrid",
    "clarification",
    "utility_spl",
]


class PipelineDispatchContract(BaseModel):
    """Stage-2 dispatch authority — built post evidence planning.

    Owns ``stage_schedule`` (ordered) and post-evidence ``llm_hops``. No parallel
    ``run_*`` / ``call_*`` booleans live here; legacy consumers derive them via
    :func:`project_dispatch_flags`.
    """

    schema_version: Literal["v1"] = "v1"
    request_mode: RequestMode = "clarification"
    stage_schedule: list[PipelineStage] = Field(default_factory=list)
    llm_hops: list[LlmHop] = Field(default_factory=list)
    slot_handoff: SlotHandoffSummary = Field(default_factory=SlotHandoffSummary)
    dispatch_reasons: list[str] = Field(default_factory=list)
    authority_holder: str = "pipeline_dispatch_v1"


class McpDiscoveryContext(BaseModel):
    indexes: list[str] = Field(default_factory=list)
    sourcetypes: list[str] = Field(default_factory=list)
    field_hints: dict[str, str] = Field(default_factory=dict)
    discovery_hops: list[dict[str, Any]] = Field(default_factory=list)
    populated_at_stage: str | None = None


class LlmSplPlanSnapshot(BaseModel):
    """Redacted detection plan the LLM chose before compile — advisory, not authority."""

    index: str | None = None
    sourcetype: str | None = None
    data_domain: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    threshold: dict[str, Any] | None = None
    detection_family: str | None = None
    consumed_by: list[str] = Field(default_factory=list)
    scheduling_trace: dict[str, Any] = Field(default_factory=dict)


class PipelineRuntimeContext(BaseModel):
    mcp_discovery_context: McpDiscoveryContext | None = None
    llm_spl_plan: LlmSplPlanSnapshot | None = None
    dispatch_cursor: PipelineStage | None = None  # last completed stage; None = not started
    mcp_phase: Literal["pre_spl", "post_spl", "none"] = "none"
    scheduling_trace: dict[str, Any] = Field(default_factory=dict)


class PipelineDispatchState(BaseModel):
    decision: PipelineDispatchContract
    runtime_context: PipelineRuntimeContext = Field(default_factory=PipelineRuntimeContext)


def project_dispatch_flags(decision: PipelineDispatchContract) -> dict[str, bool]:
    """Sole bridge from the contract to legacy ``run_*`` / ``call_*`` booleans.

    ``call_2c_llm`` is NEVER projected here — it lives on IntentDispatchDecision.
    """
    stages = set(decision.stage_schedule)
    hops = set(decision.llm_hops)
    return {
        "run_rag_early": PipelineStage.rag_early in stages,
        "run_pre_spl_mcp_discovery": PipelineStage.pre_spl_mcp_discovery in stages,
        "run_workflow_spl": PipelineStage.workflow_spl in stages,
        "run_spl_postprocessor": PipelineStage.spl_postprocessor in stages,
        "run_spl_source_resolve": PipelineStage.spl_source_resolve in stages,
        "run_mcp_execution": PipelineStage.mcp_execution in stages,
        "run_mitre_finalize": PipelineStage.mitre_finalize in stages,
        "run_cve_adapter": PipelineStage.cve_adapter in stages,
        "call_mcp_tool_planner": LlmHop.mcp_tool_planner in hops,
        "call_spl_llm": LlmHop.spl_plan_compiler in hops,
        "call_narration_llm": LlmHop.narration in hops,
    }


def next_stage_after(
    schedule: list[PipelineStage], current: PipelineStage | None
) -> PipelineStage | None:
    """Return the next scheduled stage after ``current`` (first when ``current`` is None).

    Cursor-driven routing helper (Phase 6) — never branch on ``stage in schedule``
    membership without position.
    """
    if not schedule:
        return None
    if current is None:
        return schedule[0]
    try:
        idx = schedule.index(current)
    except ValueError:
        return None
    nxt = idx + 1
    return schedule[nxt] if nxt < len(schedule) else None


def build_pipeline_dispatch(
    *,
    evidence_plan: dict[str, Any] | None = None,
    **kwargs: Any,
) -> PipelineDispatchState:
    """Build post-evidence dispatch authority (delegates to Phase 2B builder)."""
    from app.chat.pipeline_dispatch_builder import build_pipeline_dispatch as _build

    return _build(evidence_plan=evidence_plan, **kwargs)

def decision_from_state(state: dict[str, Any] | None) -> PipelineDispatchContract | None:
    """Parse ``pipeline_dispatch.decision`` from chat state when present."""
    if not isinstance(state, dict):
        return None
    dispatch = state.get("pipeline_dispatch")
    if not isinstance(dispatch, dict):
        return None
    decision = dispatch.get("decision")
    if not isinstance(decision, dict):
        return None
    try:
        return PipelineDispatchContract.model_validate(decision)
    except Exception:
        return None


def projected_flags_from_state(state: dict[str, Any] | None) -> dict[str, bool] | None:
    """Project dispatch contract flags when dispatch v2 is enabled and decision exists."""
    from app.config import settings

    if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return None
    decision = decision_from_state(state)
    if decision is None:
        return None
    return project_dispatch_flags(decision)


def imperative_hook_schedule_from_state(state: dict[str, Any] | None) -> list[str] | None:
    """Map ``stage_schedule`` to imperative pipeline hook names (REV5-A)."""
    from app.config import settings

    if not bool(getattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)):
        return None
    decision = decision_from_state(state)
    if decision is None or not decision.stage_schedule:
        return None

    hooks: list[str] = []
    for stage in decision.stage_schedule:
        if stage is PipelineStage.rag_early:
            if not hooks:
                hooks.append("prepare_rag_only")
            if "rag_early" not in hooks:
                hooks.append("rag_early")
        elif stage is PipelineStage.pre_spl_mcp_discovery:
            continue
        elif stage is PipelineStage.workflow_spl:
            if "workflow_spl" not in hooks:
                hooks.append("workflow_spl")
        elif stage is PipelineStage.spl_postprocessor:
            continue
        elif stage is PipelineStage.spl_source_resolve:
            if "spl_source_resolve" not in hooks:
                hooks.append("spl_source_resolve")
        elif stage is PipelineStage.mcp_execution:
            if "execution" not in hooks:
                hooks.append("execution")
        elif stage in {PipelineStage.mitre_finalize, PipelineStage.cve_adapter}:
            continue
    return hooks

