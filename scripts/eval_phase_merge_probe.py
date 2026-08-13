#!/usr/bin/env python3
"""Plan 5 C2 — does the phase-contract merge still drop a lifecycle stage?

Plan 3 A0 measured that making the ResourcePlan compiler authoritative *without*
a lifecycle contract drops a stage on **4 of 5 probes**: dispatch-v2 emits
`spl_postprocessor` on every SPL probe and `reference_finalize` on the MITRE
probe, while `SCHEDULABLE_HOOKS` contains neither, and `compiler_only` was empty
everywhere. That measurement was produced by an uncommitted `/tmp` script, so it
could not be re-run. This probe commits the comparison.

For each archetype it drives three producers as pure functions over the same
inputs — no connector, no LLM, no graph, no chat call:

  v2       dispatch-v2 stage projection (`imperative_hook_schedule_from_state`)
  compiler `compile_execution_schedule` alone (the pre-C1 behaviour)
  merged   PhasePolicy → PhaseContract → `merge_schedule` (Plan 5 C1)

`dropped` is `v2 - producer`: a lifecycle stage the producer would lose.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_phase_merge_probe.py
  PYTHONPATH=backend:. python3 scripts/eval_phase_merge_probe.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

DEFAULT_OUT = REPO_ROOT / "docs" / "evals" / "plan5" / "c2_phase_merge_probe.json"


def _probes() -> list[dict[str, Any]]:
    """Five archetypes mirroring Plan 3 A0: 3 SPL, 1 MITRE/reference, 1 knowledge."""
    return [
        {
            "probe_id": "t0_smb_spl",
            "answer_goal": "live_results",
            "intent_family": "live_investigation",
            "required_capabilities": ["spl", "mcp"],
            "purposes": ["spl_artifact", "mcp_execution"],
            "needs": {"needs_spl": True, "needs_mcp": True},
        },
        {
            "probe_id": "t1_spl_artifact",
            "answer_goal": "spl_artifact",
            "intent_family": "spl_generation_only",
            "required_capabilities": ["spl"],
            "purposes": ["spl_artifact"],
            "needs": {"needs_spl": True},
        },
        {
            "probe_id": "novel_identity_hunt",
            "answer_goal": "live_results",
            "intent_family": "live_investigation",
            "required_capabilities": ["spl", "mcp"],
            "purposes": ["knowledge_retrieval", "spl_artifact", "mcp_execution"],
            "needs": {"needs_rag": True, "needs_spl": True, "needs_mcp": True},
        },
        {
            "probe_id": "mitre_reference",
            "answer_goal": "reference_lookup",
            "intent_family": "reference_knowledge",
            "required_capabilities": [],
            "purposes": ["knowledge_retrieval"],
            "needs": {"needs_rag": True, "needs_mitre": True},
        },
        {
            "probe_id": "knowledge_only",
            "answer_goal": "policy_citation",
            "intent_family": "knowledge_only",
            "required_capabilities": [],
            "purposes": ["knowledge_retrieval"],
            "needs": {"needs_rag": True},
        },
    ]


def _resolved_contract(probe: dict[str, Any]):
    from app.chat.contracts.resolved_query import ResolvedQueryContract

    return ResolvedQueryContract(
        normalized_goal=probe["probe_id"],
        intent_family=probe["intent_family"],
        answer_goal=probe["answer_goal"],
        ambiguity_state="unambiguous",
        qualification_tier="T1",
        qualification_source="probe",
        required_capabilities=set(probe["required_capabilities"]),
    )


def _plan(probe: dict[str, Any]):
    from app.planner.resource_plan import PlanStep, ResourcePlan
    from app.planner.resource_plan_execution import StepExecutionSpec

    steps = []
    spl_ids: list[str] = []
    for index, purpose in enumerate(probe["purposes"]):
        step_id = f"s{index}"
        depends = spl_ids if purpose == "mcp_execution" else []
        steps.append(
            PlanStep(
                step_id=step_id,
                resource_id=f"r.{step_id}",
                purpose=purpose,
                execution=StepExecutionSpec(depends_on=list(depends), max_attempts=1),
            )
        )
        if purpose == "spl_artifact":
            spl_ids.append(step_id)
    return ResourcePlan(steps=steps)


def _v2_hooks(probe: dict[str, Any]) -> list[str]:
    """Dispatch-v2 stage projection, mapped into hook vocabulary."""
    from app.chat.contracts.pipeline_dispatch import PipelineStage
    from app.chat.pipeline_dispatch_builder import _SPL_CHAIN

    stages: list[PipelineStage] = []
    needs = probe["needs"]
    if needs.get("needs_rag"):
        stages.append(PipelineStage.rag_early)
    if needs.get("needs_spl"):
        stages.extend(_SPL_CHAIN)
    if needs.get("needs_mcp"):
        stages.append(PipelineStage.mcp_execution)
    if needs.get("needs_mitre"):
        stages.append(PipelineStage.mitre_finalize)
    if probe["answer_goal"].startswith("reference"):
        stages.append(PipelineStage.reference_finalize)

    hooks: list[str] = []
    for stage in stages:
        if stage is PipelineStage.rag_early:
            hooks.extend(["prepare_rag_only", "rag_early"])
        elif stage in {PipelineStage.mitre_finalize, PipelineStage.cve_adapter}:
            continue  # neither hook loop can run these — the C0 ownership gap
        elif stage is PipelineStage.mcp_execution:
            hooks.append("execution")
        else:
            hooks.append(stage.value)
    return hooks


def run_probes() -> dict[str, Any]:
    from app.planner.phase_contract import resolve_and_freeze
    from app.planner.phase_schedule_merge import merge_schedule
    from app.planner.resource_plan_execution_scheduler import (
        ScheduleInputs,
        compile_execution_schedule,
    )

    inputs = ScheduleInputs(blocked_step_ids=frozenset(), has_workflow_plan=False)
    rows: list[dict[str, Any]] = []

    for probe in _probes():
        contract = _resolved_contract(probe)
        plan = _plan(probe)
        v2 = _v2_hooks(probe)

        compiled, compile_reason = compile_execution_schedule(plan, inputs)
        compiler_hooks = list(compiled.hooks) if compiled else []

        phase_contract = resolve_and_freeze(contract, plan)
        merged, merge_reason = merge_schedule(contract, plan, phase_contract, inputs)
        merged_hooks = list(merged.hooks) if merged else []

        rows.append(
            {
                "probe_id": probe["probe_id"],
                "v2_hooks": v2,
                "compiler_hooks": compiler_hooks,
                "compiler_downgrade": compile_reason,
                "merged_hooks": merged_hooks,
                "merge_downgrade": merge_reason,
                "compiler_dropped": sorted(set(v2) - set(compiler_hooks)),
                "merged_dropped": sorted(set(v2) - set(merged_hooks)),
                "inline_phases": list(merged.inline_phases) if merged else [],
                "capability_satisfied": merged.capability.satisfied if merged else None,
            }
        )

    compiler_drops = sum(1 for row in rows if row["compiler_dropped"])
    merged_drops = sum(1 for row in rows if row["merged_dropped"])
    return {
        "schema_version": "plan5_c2_phase_merge_probe_v1",
        "probe_count": len(rows),
        "compiler_only_stage_drops": compiler_drops,
        "merged_stage_drops": merged_drops,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the merged schedule drops any lifecycle stage",
    )
    args = parser.parse_args()

    payload = run_probes()
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    for row in payload["rows"]:
        print(
            f"  {row['probe_id']:22} compiler_dropped={row['compiler_dropped']} "
            f"merged_dropped={row['merged_dropped']}"
        )
    print(
        f"phase_merge_probe: compiler_only_stage_drops="
        f"{payload['compiler_only_stage_drops']}/{payload['probe_count']} "
        f"merged_stage_drops={payload['merged_stage_drops']}/{payload['probe_count']}"
    )
    if args.check and payload["merged_stage_drops"]:
        print("RESULT: FAIL (the merged schedule drops a contracted lifecycle stage)")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
