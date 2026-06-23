#!/usr/bin/env python3
"""P2-B 20-row stratified causal pilot — offline role-plan gate.

Builds the deterministic hybrid role graph for each pilot row (no live LLM) and
reports which roles would run. This is the cost-bounded ablation scaffold from
plan §4.6 before live profile-1/2/3 paired runs.

Usage:
  PYTHONPATH=backend:. python3 scripts/run_p2b_causal_pilot.py
  PYTHONPATH=backend:. python3 scripts/run_p2b_causal_pilot.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (str(REPO / "backend"), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.chat.guidance_templates import should_skip_llm_composer
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.llm.hybrid_role_graph import build_hybrid_role_plan
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding

BANK = REPO / "docs/evals/p2b_causal_pilot_20_bank.json"
REPORT = REPO / "docs/evals/p2b_causal_pilot_20_report.json"


def _plan_for_row(row: dict) -> dict:
    q = row["question"]
    u = understand_query(q)
    qti = build_query_to_intent(query=q, query_understanding=u)
    intent = qti.intent_classification.model_dump() if qti.intent_classification else {}
    skip_comp, skip_reason = should_skip_llm_composer(
        query=q,
        path_type=None,
        intent_family=intent.get("intent_family"),
    )
    route, _ = select_route_from_understanding(u, q)
    plan = build_hybrid_role_plan(
        query=q,
        match_path=u.deterministic_match_path,
        selected_skill=str(route.get("skill") or "knowledge_recall"),
        answer_contract=None,
        path_type=None,
        intent_family=intent.get("intent_family"),
        draft_preview_active=False,
        skip_composer=skip_comp,
        skip_composer_reason=skip_reason,
        intent_advisory_skipped=True,
        intent_skip_reason="pilot_offline",
        control_plane_enabled=bool(settings.control_plane_enabled),
        soc_investigation_shaped=bool(u.soc_investigation_shaped),
    )
    enabled = [r.role_id for r in plan.roles if r.enabled]
    return {
        "id": row["id"],
        "category": row["category"],
        "stratum": row.get("stratum"),
        "complexity_tier": plan.complexity_tier,
        "deadline_seconds": plan.deadline_seconds,
        "enabled_roles": enabled,
        "plan": plan.to_trace_dict(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit non-zero if gate fails")
    args = ap.parse_args()

    bank = json.loads(BANK.read_text())
    results = [_plan_for_row(r) for r in bank["rows"]]
    boundary = [r for r in results if r["stratum"] in {"unsafe_execution", "out_of_scope", "boundary_refusal"} or "boundary" in r["category"]]
    failures: list[str] = []
    role_dist = dict(Counter(role for r in results for role in r["enabled_roles"]))
    complexity_dist = dict(Counter(r["complexity_tier"] for r in results))

    for r in results:
        if r["id"] in {"eff.072", "eff.099", "eff.098"}:
            if r["enabled_roles"]:
                failures.append(f"{r['id']}: boundary row must not enable LLM roles")
        elif not r["enabled_roles"]:
            failures.append(f"{r['id']}: non-boundary row has zero enabled roles")

    report = {
        "row_count": len(results),
        "role_distribution": role_dist,
        "complexity_distribution": complexity_dist,
        "failures": failures,
        "rows": results,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")

    print(f"p2b_causal_pilot: {len(results)} rows, failures={len(failures)}")
    print(f"  role_distribution: {report['role_distribution']}")
    if failures:
        for f in failures:
            print(f"  FAIL {f}")
    if args.check and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
