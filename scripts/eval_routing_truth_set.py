#!/usr/bin/env python3
"""Routing truth-set evaluator (Plan 4 R1.4) — deterministic, in-process, no LLM.

Scores production routing against the independently-labelled truth set. Two
verdicts per row, deliberately independent:

  route_ok / route_wrong   selected skill in the row's `acceptable_skills` set
  capability_inconsistent  the selected skill's contract denies a capability the
                           row's LABEL marks required -- reported even when the
                           route is acceptable, and regardless of whether the
                           final answer would still match an answer golden

`expected_intent_family` and `expected_answer_shape` are REPORTED, never gated.
R1.3 measured two independent labellers at 20/20 on both gating axes but 9/20 on
intent family, with 0 of 11 family differences crossing a capability boundary --
so family disagreement carries no routing information and gating it would invent
a ~55% failure rate out of vocabulary granularity.

`--check` is NO-REGRESSION against a baseline, not identity: a row may not flip
route_ok -> route_wrong, and may not gain capability_inconsistent. Improvements
pass. Identity-checking would pass trivially at R1.5 and fail by construction
once R3/R2 improve on the baseline.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --json out.json
  PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --check --baseline docs/evals/routing_truth_set_baseline_v1.json
  PYTHONPATH=backend:. python3 scripts/eval_routing_truth_set.py --freeze docs/evals/routing_truth_set_baseline_v1.json
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

DEFAULT_TRUTH_SET = REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json"
DEFAULT_BASELINE = REPO_ROOT / "docs" / "evals" / "routing_truth_set_baseline_v1.json"

SCHEMA_VERSION = "2026-08-12-routing-eval-v1"


ARM_DETERMINISTIC = "deterministic"
ARM_LIVE = "live"
ARM_BOTH = "both"


def _granted_capabilities(skill: str | None) -> frozenset[str]:
    """Capabilities a skill's contract grants, via the one permit primitive."""
    from app.chat.skill_intent_compatibility import _contract_grants, skill_contract_for

    contract = skill_contract_for(skill)
    return frozenset(cap for cap in ("spl", "mcp") if _contract_grants(contract, cap))


def evaluate_live_row(row: dict[str, Any], deterministic_skill: str | None) -> dict[str, Any]:
    """Route one row through `route_skill` — the production-final path.

    The deterministic arm measures `select_route_from_understanding`, which is the
    layer Plan 4's corrections modify. It is not what the host obeys on
    out-of-registry paths, where a validated LLM advisory can replace the skill.
    Reporting both is what keeps every later claim honest about which layer it
    measured.
    """
    from app.routing.skill_router import route_skill

    try:
        live = route_skill(str(row["query"]))
    except Exception as exc:  # noqa: BLE001 - an unroutable row is data, not a crash
        return {
            "live_skill": None,
            "live_selected_by": f"<error {type(exc).__name__}>",
            "live_error": str(exc),
            "live_route_verdict": "route_wrong",
            "live_diverges": True,
            "live_delta": "error",
        }

    live_skill = live.get("skill")
    acceptable = set(row["acceptable_skills"])
    det_ok = deterministic_skill in acceptable
    live_ok = live_skill in acceptable

    det_caps = _granted_capabilities(deterministic_skill)
    live_caps = _granted_capabilities(live_skill)
    lost = det_caps - live_caps

    if live_skill == deterministic_skill:
        delta = "same"
    elif det_ok and not live_ok:
        delta = "degraded"
    elif live_ok and not det_ok:
        delta = "improved"
    else:
        delta = "lateral"

    return {
        "live_skill": live_skill,
        "live_selected_by": live.get("selected_by"),
        "live_confidence": live.get("confidence"),
        "live_route_verdict": "route_ok" if live_ok else "route_wrong",
        "live_diverges": live_skill != deterministic_skill,
        "live_delta": delta,
        # A capability downgrade is measured against the *contracts*, not against
        # the label: the advisory swapped in a skill that grants strictly less.
        "live_capability_downgrade": bool(lost),
        "live_capabilities_lost": sorted(lost),
        "live_capabilities_gained": sorted(live_caps - det_caps),
        "advisory_selected": live.get("selected_by") == "llm_advisory_validated",
    }


def evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
    from app.chat.evidence_planner import plan_evidence
    from app.chat.intent_classifier import build_query_to_intent
    from app.chat.planning_decision import plan_path_and_tools
    from app.evals.routing_truth_set import capability_consistency
    from app.query_understanding.parser import understand_query
    from app.routing.select_route_from_understanding import select_route_from_understanding

    query = str(row["query"])
    understanding = understand_query(query)
    base, provenance = select_route_from_understanding(understanding, query)
    selected = base.get("skill")

    result = build_query_to_intent(query=query, query_understanding=understanding, routed_skill=selected)
    intent = result.intent_classification
    plan = plan_evidence(intent, query_to_intent=result.model_dump(), query_understanding=understanding, routed=base)
    decision = plan_path_and_tools(
        intent_classification=intent.model_dump(),
        evidence_plan=plan.model_dump(),
        routed=base,
        query_understanding=understanding,
    )

    route_ok = selected in set(row["acceptable_skills"])
    consistent, denied = capability_consistency(
        selected_skill=selected, required_capabilities=row["required_capabilities"]
    )

    return {
        "row_id": row["row_id"],
        "quotas": list(row.get("quotas", [])),
        "ambiguous": bool(row["ambiguous"]),
        "label_confidence": row["label_confidence"],
        # gating
        "route_verdict": "route_ok" if route_ok else "route_wrong",
        "capability_inconsistent": not consistent,
        "denied_capabilities": sorted(denied),
        # observed
        "selected_skill": selected,
        "acceptable_skills": sorted(row["acceptable_skills"]),
        "required_capabilities": sorted(row["required_capabilities"]),
        "authority_source": provenance.get("authority_source"),
        "match_path": understanding.deterministic_match_path,
        "route_confidence": base.get("confidence"),
        # reported, never gated
        "observed_intent_family": intent.intent_family,
        "expected_intent_family": row["expected_intent_family"],
        "family_match": intent.intent_family == row["expected_intent_family"],
        "observed_path_type": decision.path_type,
        "observed_answer_mode": plan.answer_mode,
        "expected_answer_shape": row["expected_answer_shape"],
        "needs_spl": bool(plan.needs_spl),
        "execution_enabled": bool(decision.execution_enabled),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gating = [r for r in rows if not r["ambiguous"]]
    ok = [r for r in gating if r["route_verdict"] == "route_ok"]
    inconsistent = [r for r in gating if r["capability_inconsistent"]]

    def in_quota(name: str) -> list[dict[str, Any]]:
        return [r for r in gating if name in r["quotas"]]

    # Knowledge-only false escalation: a row whose label needs no execution
    # capability but which the planner still drives toward SPL.
    false_escalation = [
        r for r in gating if not r["required_capabilities"] and r["needs_spl"]
    ]
    # Hunt under-routing: label needs SPL, but the selected skill cannot provide it.
    under_routed = [
        r for r in gating if "spl" in r["required_capabilities"] and r["capability_inconsistent"]
    ]
    # Unsafe containment: every clarification-labelled row must stay non-executing.
    unsafe_rows = [r for r in gating if r["expected_answer_shape"] == "clarification"]
    contained = [r for r in unsafe_rows if not r["execution_enabled"]]

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "total_rows": len(rows),
        "gating_rows": len(gating),
        "ambiguous_rows": len(rows) - len(gating),
        "route_ok": len(ok),
        "route_wrong": len(gating) - len(ok),
        "route_correct_rate": round(len(ok) / len(gating), 4) if gating else None,
        "capability_inconsistent": len(inconsistent),
        "capability_inconsistent_rate": round(len(inconsistent) / len(gating), 4) if gating else None,
        "knowledge_only_false_escalation": len(false_escalation),
        "hunt_under_routing": len(under_routed),
        "unsafe_rows": len(unsafe_rows),
        "unsafe_contained": len(contained),
        "by_quota": {
            name: {
                "rows": len(in_quota(name)),
                "route_ok": sum(1 for r in in_quota(name) if r["route_verdict"] == "route_ok"),
                "capability_inconsistent": sum(1 for r in in_quota(name) if r["capability_inconsistent"]),
            }
            for name in sorted({q for r in gating for q in r["quotas"]})
        },
        # reported only
        "family_match_reported": sum(1 for r in gating if r["family_match"]),
    }
    if any("live_skill" in r for r in gating):
        live = [r for r in gating if "live_skill" in r]
        summary["live_arm"] = {
            "rows": len(live),
            "advisory_selected": sum(1 for r in live if r.get("advisory_selected")),
            "diverges_from_deterministic": sum(1 for r in live if r.get("live_diverges")),
            "degraded": sum(1 for r in live if r.get("live_delta") == "degraded"),
            "improved": sum(1 for r in live if r.get("live_delta") == "improved"),
            "lateral": sum(1 for r in live if r.get("live_delta") == "lateral"),
            "capability_downgrades": sum(1 for r in live if r.get("live_capability_downgrade")),
            "live_route_ok": sum(1 for r in live if r.get("live_route_verdict") == "route_ok"),
            "selected_by": _count_by(live, "live_selected_by"),
        }
    return summary


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row.get(key))] = counts.get(str(row.get(key)), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def compare(current: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> list[str]:
    """No-regression comparison. Improvements are allowed; regressions are not."""
    base_by_id = {r["row_id"]: r for r in baseline}
    failures: list[str] = []
    for row in current:
        prior = base_by_id.get(row["row_id"])
        if prior is None:
            continue  # a new row cannot regress against a baseline that lacks it
        if row["ambiguous"]:
            continue
        if prior["route_verdict"] == "route_ok" and row["route_verdict"] == "route_wrong":
            failures.append(
                f"{row['row_id']}: route regressed to {row['selected_skill']!r} "
                f"(acceptable: {row['acceptable_skills']})"
            )
        if row["capability_inconsistent"] and not prior["capability_inconsistent"]:
            failures.append(
                f"{row['row_id']}: newly capability_inconsistent, "
                f"{row['selected_skill']!r} denies {row['denied_capabilities']}"
            )
    missing = sorted(set(base_by_id) - {r["row_id"] for r in current})
    if missing:
        failures.append(f"rows present in baseline but missing from this run: {missing}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-set", type=Path, default=DEFAULT_TRUTH_SET)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--arm",
        choices=[ARM_DETERMINISTIC, ARM_LIVE, ARM_BOTH],
        default=ARM_DETERMINISTIC,
        help="deterministic = the layer Plan 4 modifies (default, and the gated arm); "
        "live = production-final route_skill; both = report the delta",
    )
    parser.add_argument("--check", action="store_true", help="exit 1 on any regression vs baseline")
    parser.add_argument("--json", dest="json_out", type=Path, default=None)
    parser.add_argument("--freeze", type=Path, default=None, help="write this run as a new baseline")
    args = parser.parse_args()

    from app.evals.routing_truth_set import STAGE_LABELED, validate_rows

    payload = json.loads(args.truth_set.read_text(encoding="utf-8"))
    if payload.get("stage") != STAGE_LABELED:
        print(f"RESULT: FAIL (truth set stage is {payload.get('stage')!r}, expected 'labeled')")
        return 1
    invalid = [r for r in validate_rows(payload["rows"], stage=STAGE_LABELED) if not r.ok]
    if invalid:
        for item in invalid:
            print(f"  invalid row {item.row_id}: {item.errors}")
        print(f"RESULT: FAIL (0/{len(payload['rows'])} rows, truth set failed schema validation)")
        return 1

    rows = []
    for row in payload["rows"]:
        result = evaluate_row(row)
        if args.arm in (ARM_LIVE, ARM_BOTH):
            result.update(evaluate_live_row(row, result["selected_skill"]))
        rows.append(result)
    summary = summarize(rows)
    report = {"summary": summary, "rows": rows}

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    if args.freeze:
        args.freeze.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(f"froze baseline -> {args.freeze}")

    print(
        f"routing_truth_set: gating={summary['gating_rows']} ambiguous={summary['ambiguous_rows']} "
        f"route_ok={summary['route_ok']} route_wrong={summary['route_wrong']} "
        f"capability_inconsistent={summary['capability_inconsistent']} "
        f"false_escalation={summary['knowledge_only_false_escalation']} "
        f"under_routing={summary['hunt_under_routing']} "
        f"unsafe_contained={summary['unsafe_contained']}/{summary['unsafe_rows']} "
        f"family_match_reported={summary['family_match_reported']}/{summary['gating_rows']}"
    )

    live = summary.get("live_arm")
    if live:
        print(
            f"  live_arm: advisory_selected={live['advisory_selected']}/{live['rows']} "
            f"diverges={live['diverges_from_deterministic']} degraded={live['degraded']} "
            f"improved={live['improved']} lateral={live['lateral']} "
            f"capability_downgrades={live['capability_downgrades']} "
            f"live_route_ok={live['live_route_ok']}/{live['rows']}"
        )

    failures: list[str] = []
    if args.check:
        if not args.baseline.is_file():
            print(f"RESULT: FAIL (0/{summary['gating_rows']} rows, baseline {args.baseline} not found)")
            return 1
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))["rows"]
        failures = compare(rows, baseline)
        for line in failures:
            print(f"  REGRESSION {line}")

    verdict = "FAIL" if failures else "PASS"
    detail = f"{summary['route_ok']}/{summary['gating_rows']} route_ok"
    if args.check:
        detail += f", {len(failures)} regressions vs baseline"
    print(f"RESULT: {verdict} ({detail})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
