#!/usr/bin/env python3
"""Plan 7 A1 — structural population sweep for lost mandatory lifecycle work.

Measures the **planning layer** directly rather than replaying `/chat`: for every
corpus query it builds the same `ResolvedQueryContract` and `ResourcePlan` the
runtime builds, resolves the `PhaseContract`, then runs the real compiler and the
real merge. That is exactly the triple whose interaction produces the defect, and
it costs no LLM call, no MCP call and no HTTP turn.

Structural condition being counted:

    PhaseContract declares an applicable MANDATORY lifecycle phase
      + compiler returns a downgrade (no_schedulable_step or equivalent)
      + merge therefore never applies the PhaseContract
      + the mandatory work has no other owner with dispatch-v2 OFF

Classification is by **mechanism and phase type**, never by query ID.

    python3 scripts/eval_plan7_a1_population.py --corpus all
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "backend", ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.chat.evidence_planner import plan_evidence  # noqa: E402
from app.chat.intent_classifier import build_query_to_intent  # noqa: E402
from app.chat.resolved_query_builder import build_resolved_query_contract  # noqa: E402
from app.planner.phase_contract import resolve_and_freeze  # noqa: E402
from app.planner.phase_policy import PhasePolicyInputs  # noqa: E402
from app.planner.phase_schedule_merge import merge_schedule  # noqa: E402
from app.planner.composer import compose_resource_plan  # noqa: E402
from app.planner.resource_plan_authority import resource_plan_authority  # noqa: E402
from app.planner.resource_plan import ResourcePlan  # noqa: E402
from app.planner.resource_plan_execution_scheduler import (  # noqa: E402
    ScheduleInputs,
    compile_execution_schedule,
)
from app.query_understanding.parser import understand_query  # noqa: E402
from app.routing.skill_router import route_skill  # noqa: E402

# dispatch-v2 OFF is the posture under audit: pre-SPL discovery is not applicable
# and there is no projected schedule for a phase to be inherited from.
POLICY = PhasePolicyInputs(has_workflow_plan=False, pre_spl_discovery_enabled=False)
INPUTS = ScheduleInputs(blocked_step_ids=frozenset(), has_workflow_plan=False)


def _analyse(query: str) -> dict[str, Any]:
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    evidence_plan = plan_evidence(
        q2i.intent_classification,
        query_to_intent=q2i.model_dump(),
        query_understanding=understanding,
    )
    # The routed skill's capability contract vetoes steps during composition, so
    # a sweep that omits it measures a plan the runtime never builds.
    try:
        routed = route_skill(query)
        routed_skill = str(routed.get("skill") or "") or None
    except Exception:  # noqa: BLE001 - routing failure is data
        routed_skill = None

    payload = evidence_plan.model_dump()
    raw_plan = payload.get("resource_plan")
    plan = None
    plan_error = None
    if isinstance(raw_plan, dict):
        try:
            plan = ResourcePlan.model_validate(raw_plan)
        except Exception as exc:  # noqa: BLE001 - an unparseable plan is data
            plan_error = type(exc).__name__
    if plan is None:
        # `plan_evidence` decides the evidence needs; composition into a
        # ResourcePlan happens later in the runtime. Compose it here with the
        # same composer the graph uses, so the sweep measures a real plan rather
        # than the absence of one.
        try:
            # Composition is authority-gated to the runtime's approved scope. The
            # sweep enters that scope explicitly so it measures the same composer
            # the runtime uses; it commits nothing and touches no state.
            with resource_plan_authority():
                plan = compose_resource_plan(
                    evidence_plan,
                    intent_family=q2i.intent_classification.intent_family,
                    skill_id=routed_skill,
                )
        except Exception as exc:  # noqa: BLE001 - a composition failure is data
            plan_error = type(exc).__name__

    contract = build_resolved_query_contract(
        query=query,
        query_understanding=understanding,
        qualification_tier=getattr(understanding, "catalogue_tier", None) or "T4",
        qualification_source="a1_population_sweep",
        query_to_intent=q2i,
    )

    phase_contract = resolve_and_freeze(contract, plan, POLICY)
    mandatory = [phase for phase in phase_contract.phases if phase.mandatory]
    mandatory_names = sorted(phase.name for phase in mandatory)
    hook_backed = sorted(phase.name for phase in mandatory if phase.hook_name is not None)
    inline_only = sorted(phase.name for phase in mandatory if phase.hook_name is None)

    compiled, downgrade = compile_execution_schedule(plan, INPUTS)
    merged, merge_reason = merge_schedule(contract, plan, phase_contract, INPUTS)
    represented = set(merged.hooks) | set(merged.inline_phases) if merged is not None else set()

    # The defect: the contract owes hook-backed lifecycle work, the merge produced
    # nothing, and the reason is a bare compiler downgrade.
    affected = merged is None and bool(hook_backed) and downgrade is not None

    return {
        "intent_family": contract.intent_family,
        "answer_goal": contract.answer_goal,
        "qualification_tier": contract.qualification_tier,
        "required_capabilities": sorted(contract.required_capabilities or []),
        "routed_skill": routed_skill,
        "has_plan": plan is not None,
        "plan_error": plan_error,
        "plan_purposes": sorted({str(step.purpose) for step in plan.steps}) if plan else [],
        "mandatory": mandatory_names,
        "mandatory_hook_backed": hook_backed,
        "mandatory_inline_only": inline_only,
        "compile_downgrade": downgrade,
        "compiled_hooks": list(compiled.hooks) if compiled is not None else None,
        "merge_reason": merge_reason,
        "merged": merged is not None,
        "merged_hooks": list(merged.hooks) if merged is not None else None,
        "mandatory_lost": sorted(set(mandatory_names) - represented),
        "affected": affected,
    }


def _load_corpus(name: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if name in {"plan6", "all"}:
        payload = json.loads(
            (ROOT / "docs" / "evals" / "plan6" / "vps_corpus_v1.json").read_text("utf-8")
        )
        entries = payload["rows"] if isinstance(payload, dict) else payload
        for row in entries:
            rows.append(("plan6_corpus", str(row["row_id"]), str(row["query"])))
    if name in {"golden105", "all"}:
        payload = json.loads(
            (ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json").read_text(
                "utf-8"
            )
        )
        for entry in payload["entries"]:
            rows.append(("golden_105", str(entry["question_ref"]), str(entry["question"])))
    if name in {"cisco50", "all"}:
        payload = json.loads(
            (ROOT / "docs" / "evals" / "cisco_powergrid_question_bank.json").read_text("utf-8")
        )
        for row in payload["entries"]:
            rows.append(("cisco_50", str(row["question_id"]), str(row["question"])))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="all", choices=["all", "plan6", "golden105", "cisco50"])
    parser.add_argument("--out", default="docs/evals/plan7/a1_structural_population.json")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = _load_corpus(args.corpus)
    if args.limit:
        rows = rows[: args.limit]

    results: list[dict[str, Any]] = []
    for corpus, row_id, query in rows:
        try:
            record = _analyse(query)
        except Exception as exc:  # noqa: BLE001 - a failing row is data, not a crash
            record = {"error": f"{type(exc).__name__}: {exc}"[:200], "affected": False}
        record["corpus"] = corpus
        record["row_id"] = row_id
        results.append(record)

    affected = [row for row in results if row.get("affected")]
    by_phase: Counter[str] = Counter()
    for row in affected:
        by_phase.update(row.get("mandatory_hook_backed") or [])

    summary = {
        "total_rows": len(results),
        "affected_rows": len(affected),
        "affected_by_corpus": dict(Counter(row.get("corpus") for row in affected)),
        "affected_by_mechanism": dict(Counter(row.get("compile_downgrade") for row in affected)),
        "affected_by_lost_phase": dict(by_phase),
        "affected_by_intent_family": dict(Counter(row.get("intent_family") for row in affected)),
        "compile_downgrade_all_rows": dict(
            Counter(row.get("compile_downgrade") for row in results)
        ),
        "merged_rows": sum(1 for row in results if row.get("merged")),
        "errors": sum(1 for row in results if row.get("error")),
    }

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": results}, indent=2) + "\n", "utf-8")
    print(json.dumps(summary, indent=2))
    print(json.dumps({"ok": True, "out": str(out.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
