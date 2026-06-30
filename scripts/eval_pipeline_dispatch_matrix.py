#!/usr/bin/env python3
"""Pipeline dispatch matrix evaluation (Phase 8).

Walks representative query classes through build_pipeline_dispatch and verifies
the request_mode -> stage_schedule + llm_hops contract. Non-gating observation in
the governance regression first; promote to gating after burn-in.

Usage:
    PYTHONPATH=backend:. python3 scripts/eval_pipeline_dispatch_matrix.py --check
"""

from __future__ import annotations

import argparse
import sys

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


def _decision(plan: EvidencePlan, family: str):
    return build_pipeline_dispatch(
        evidence_plan=plan.model_dump(), intent_classification={"intent_family": family}
    ).decision


_CASES = [
    (
        "mitre_explain",
        _plan(needs_rag=True, needs_mitre=True),
        "mitre_explanation",
        lambda d: d.request_mode == "mitre_knowledge"
        and PipelineStage.mitre_finalize in d.stage_schedule
        and PipelineStage.workflow_spl not in d.stage_schedule,
    ),
    (
        "cve_review",
        _plan(needs_rag=True),
        "cve_investigation",
        lambda d: d.request_mode == "cve_review" and PipelineStage.cve_adapter in d.stage_schedule,
    ),
    (
        "sop_playbook",
        _plan(needs_rag=True),
        "sop_or_playbook",
        lambda d: d.request_mode == "knowledge" and d.stage_schedule == [PipelineStage.rag_early],
    ),
    (
        "hybrid_alert",
        _plan(
            answer_mode="hybrid",
            needs_rag=True,
            needs_spl=True,
            spl_allowed=True,
            needs_mitre=True,
            normalized_slot_summary={"normalized_slots": {"index": "i", "sourcetype": "s"}},
        ),
        "hybrid_alert_review",
        lambda d: d.request_mode == "hybrid"
        and PipelineStage.workflow_spl in d.stage_schedule
        and PipelineStage.mitre_finalize in d.stage_schedule,
    ),
    (
        "spl_authoring_bound_slots",
        _plan(
            answer_mode="live_investigation",
            needs_spl=True,
            spl_allowed=True,
            normalized_slot_summary={"normalized_slots": {"index": "scada_perf", "sourcetype": "perf"}},
        ),
        "spl_generation_only",
        lambda d: d.request_mode == "spl_authoring"
        and PipelineStage.pre_spl_mcp_discovery not in d.stage_schedule
        and PipelineStage.workflow_spl in d.stage_schedule
        and PipelineStage.mcp_execution not in d.stage_schedule,
    ),
]


def _postprocessor_invariant(d) -> bool:
    if PipelineStage.workflow_spl not in d.stage_schedule:
        return True
    i = d.stage_schedule.index(PipelineStage.workflow_spl)
    return (
        i + 1 < len(d.stage_schedule)
        and d.stage_schedule[i + 1] == PipelineStage.spl_postprocessor
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit non-zero on any failure")
    args = ap.parse_args()

    failures: list[str] = []
    for name, plan, family, predicate in _CASES:
        d = _decision(plan, family)
        ok = predicate(d) and _postprocessor_invariant(d)
        status = "PASS" if ok else "FAIL"
        print(f"  {status} {name}: mode={d.request_mode} stages={[s.value for s in d.stage_schedule]}")
        if not ok:
            failures.append(name)

    total = len(_CASES)
    print(f"pipeline_dispatch_matrix: total={total} pass={total - len(failures)} fail={len(failures)}")
    if args.check and failures:
        print(f"FAIL: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("--check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
