"""Phase 8 — dispatch matrix F–J (request_mode -> stage_schedule + llm_hops).

These lock the canonical dispatch contract for representative query classes so
the schedule/hops can't silently drift. They assert on build_pipeline_dispatch
directly (deterministic) rather than a full /chat run.
"""

from __future__ import annotations

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.pipeline_dispatch import LlmHop, PipelineStage
from app.chat.pipeline_dispatch_builder import build_pipeline_dispatch


def _plan(**over) -> EvidencePlan:
    base = dict(
        answer_mode="rag_only",
        rag_phase="rag_only",
        needs_rag=False,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    )
    base.update(over)
    return EvidencePlan(**base)


def _dispatch(plan: EvidencePlan, family: str):
    return build_pipeline_dispatch(
        evidence_plan=plan.model_dump(),
        intent_classification={"intent_family": family},
    ).decision


def test_F_mitre_explain_no_spl_stages() -> None:
    d = _dispatch(_plan(answer_mode="rag_only", needs_rag=True, needs_mitre=True), "mitre_explanation")
    assert d.request_mode == "mitre_knowledge"
    assert PipelineStage.mitre_finalize in d.stage_schedule
    assert PipelineStage.workflow_spl not in d.stage_schedule
    assert PipelineStage.spl_postprocessor not in d.stage_schedule


def test_G_cve_review_has_cve_adapter() -> None:
    d = _dispatch(_plan(needs_rag=True), "cve_investigation")
    assert d.request_mode == "cve_review"
    assert PipelineStage.cve_adapter in d.stage_schedule
    assert PipelineStage.workflow_spl not in d.stage_schedule


def test_H_sop_playbook_is_rag_only() -> None:
    d = _dispatch(_plan(answer_mode="rag_only", needs_rag=True), "sop_or_playbook")
    assert d.request_mode == "knowledge"
    assert d.stage_schedule == [PipelineStage.rag_early]


def test_I_spl_meta_uses_plan_compiler_and_postprocessor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.chat.pipeline_dispatch_builder.settings.ai_soc_llm_spl_fallback_enabled", True
    )
    plan = _plan(
        answer_mode="live_investigation",
        needs_spl=True,
        spl_allowed=True,
        normalized_slot_summary={"normalized_slots": {}, "unbound_constraints": [{"slot": "index"}]},
    )
    d = _dispatch(plan, "spl_generation_only")
    assert d.request_mode == "spl_authoring"
    # workflow_spl must be immediately followed by spl_postprocessor.
    idx = d.stage_schedule.index(PipelineStage.workflow_spl)
    assert d.stage_schedule[idx + 1] == PipelineStage.spl_postprocessor
    assert LlmHop.spl_plan_compiler in d.llm_hops


def test_J_hybrid_schedules_spl_and_mitre() -> None:
    plan = _plan(
        answer_mode="hybrid",
        needs_rag=True,
        needs_spl=True,
        spl_allowed=True,
        needs_mitre=True,
        normalized_slot_summary={"normalized_slots": {"index": "pgcil_soc", "sourcetype": "wineventlog"}},
    )
    d = _dispatch(plan, "hybrid_alert_review")
    assert d.request_mode == "hybrid"
    assert PipelineStage.workflow_spl in d.stage_schedule
    assert PipelineStage.mitre_finalize in d.stage_schedule


def test_workflow_spl_always_followed_by_postprocessor_across_spl_modes() -> None:
    """Invariant: every schedule containing workflow_spl has postprocessor next."""
    cases = [
        (_plan(answer_mode="live_investigation", needs_spl=True, spl_allowed=True,
               normalized_slot_summary={"normalized_slots": {"index": "i", "sourcetype": "s"}}),
         "spl_generation_only"),
        (_plan(answer_mode="live_investigation", needs_spl=True, spl_allowed=True, needs_mcp=True, mcp_allowed=True,
               normalized_slot_summary={"normalized_slots": {"index": "i", "sourcetype": "s"}}),
         "spl_generation_and_run"),
    ]
    for plan, family in cases:
        d = _dispatch(plan, family)
        if PipelineStage.workflow_spl in d.stage_schedule:
            i = d.stage_schedule.index(PipelineStage.workflow_spl)
            assert d.stage_schedule[i + 1] == PipelineStage.spl_postprocessor, family
