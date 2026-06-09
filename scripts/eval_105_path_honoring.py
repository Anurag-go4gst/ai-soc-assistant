#!/usr/bin/env python3
"""Tier B 105-question path-honoring eval — deterministic, path-only, no LLM.

Runs every entry of question_runtime_map_v1.json through
understand_query -> intent -> evidence plan -> planner and checks path shape.
Differs from the stage3l 105 shadow eval (route agreement only): this asserts
intent_family / path_type / needs_* / severity behavior / answer_mode.

Hard gates (--check exits 1 on violation):
  * every row resolves an exact 105 match path and raises no exception
  * planner execution stays disabled on every row
  * top_n_aggregation rows: spl_generation_only intent, spl_review path,
    needs_spl=true, analytics severity guard ("Not assigned from this question
    alone"), live_investigation answer mode
  * clarification_required total must not exceed the recorded baseline
    (CLARIFICATION_BASELINE) — other pattern classes are observation-only until
    their registry honoring lands in a later batch.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py --check
  PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import plan_path_and_tools
from app.query_understanding.parser import understand_query
from app.risk.severity_policy import (
    ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL,
    apply_analytics_severity_guard,
    decide_severity,
)

MAP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
EXACT_PATHS = {"exact_105_question", "exact_105_plus_use_case_catalog"}
ROUTED_STUB = {"skill": "attack_discovery", "tool_plan": ["generate_spl", "validate_spl"]}

# Recorded 2026-06-09 after the top_n analytics + hunt-pattern bridges landed
# (was 81 before top_n, 72 before hunt). Lowering this is progress; raising it
# is a regression.
CLARIFICATION_BASELINE = 10

# Exact-105 hunt/detection classes that must reach the review-only SPL path
# (mirrors _EXACT_105_HUNT_PATTERNS in app/chat/query_signals.py).
HUNT_PATTERNS = {
    "ioc_correlation",
    "dns_beaconing_dga_behavior",
    "multi_signal_correlation",
    "new_or_unusual_source",
    "threshold_anomaly",
    "lateral_movement",
    "suspicious_process_powershell",
    "dlp_exfiltration",
    "persistence_scheduled_task_service",
    "success_after_failure",
    "other_or_unclear",
}


def evaluate_row(entry: dict[str, Any]) -> dict[str, Any]:
    query = str(entry["question"])
    understanding = understand_query(query)
    result = build_query_to_intent(query=query, query_understanding=understanding)
    intent = result.intent_classification
    plan = plan_evidence(
        intent,
        query_to_intent=result.model_dump(),
        query_understanding=understanding,
    )
    decision = plan_path_and_tools(
        intent_classification=intent.model_dump(),
        evidence_plan=plan.model_dump(),
        routed=ROUTED_STUB,
        query_understanding=understanding,
    )
    signals = result.query_signals
    severity = apply_analytics_severity_guard(
        decide_severity(None, None, []),
        analytics_query=bool(
            signals.get("exact_105_analytics")
            or signals.get("exact_105_hunt_spl")
            or signals.get("analytics_aggregation")
        ),
        alert_context_present=bool(signals.get("alert_context_present")),
    )
    return {
        "question_ref": entry["question_ref"],
        "pattern_type": entry["pattern_type"],
        "match_path": understanding.deterministic_match_path,
        "mapped_question_ref": understanding.mapped_question_ref,
        "operation_type": understanding.mapped_operation_type,
        "intent_family": intent.intent_family,
        "requires_clarification": intent.requires_clarification,
        "path_type": decision.path_type,
        "needs_spl": plan.needs_spl,
        "needs_rag": plan.needs_rag,
        "needs_mitre": plan.needs_mitre,
        "answer_mode": plan.answer_mode,
        "severity_label": severity.severity_label,
        "execution_enabled": decision.execution_enabled,
    }


def check_rows(rows: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for row in rows:
        ref = row["question_ref"]
        if row["match_path"] not in EXACT_PATHS:
            violations.append(f"{ref}: match_path={row['match_path']} (expected exact 105)")
        if row["mapped_question_ref"] != ref:
            violations.append(
                f"{ref}: mapped to {row['mapped_question_ref']} (registry self-match broken)"
            )
        if row["execution_enabled"]:
            violations.append(f"{ref}: planner execution_enabled=true")
        if row["pattern_type"] == "top_n_aggregation":
            if row["intent_family"] != "spl_generation_only":
                violations.append(f"{ref}: top_n intent={row['intent_family']}")
            if row["path_type"] != "spl_review":
                violations.append(f"{ref}: top_n path_type={row['path_type']}")
            if not row["needs_spl"]:
                violations.append(f"{ref}: top_n needs_spl=false")
            if row["answer_mode"] != "live_investigation":
                violations.append(f"{ref}: top_n answer_mode={row['answer_mode']}")
            if row["severity_label"] != ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL:
                violations.append(f"{ref}: top_n severity={row['severity_label']}")
        if row["pattern_type"] in HUNT_PATTERNS:
            # Earlier deterministic branches (e.g. success-after-failure hybrid
            # review) keep authority; the gate is only "never clarification".
            if row["intent_family"] == "clarification_required":
                violations.append(f"{ref}: hunt pattern fell to clarification")
            if row["path_type"] in {"clarification_required", "unsafe_blocked"}:
                violations.append(f"{ref}: hunt pattern path_type={row['path_type']}")
            if row["intent_family"] == "spl_generation_only" and not row["needs_spl"]:
                violations.append(f"{ref}: hunt pattern needs_spl=false")
    clarification_total = sum(1 for row in rows if row["intent_family"] == "clarification_required")
    if clarification_total > CLARIFICATION_BASELINE:
        violations.append(
            f"clarification_required rows rose to {clarification_total} "
            f"(baseline {CLARIFICATION_BASELINE})"
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 on gate violations")
    parser.add_argument("--json", type=Path, default=None, help="write per-row results JSON")
    args = parser.parse_args()

    entries = json.loads(MAP_PATH.read_text(encoding="utf-8"))["entries"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for entry in entries:
        try:
            rows.append(evaluate_row(entry))
        except Exception as exc:  # gate: any pipeline exception is a violation
            errors.append(f"{entry.get('question_ref')}: {type(exc).__name__}: {exc}")

    by_pattern: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_pattern[row["pattern_type"]][row["path_type"]] += 1
    print(f"rows evaluated: {len(rows)}/{len(entries)}; errors: {len(errors)}")
    for pattern in sorted(by_pattern):
        print(f"  {pattern}: {dict(by_pattern[pattern])}")
    clarification_total = sum(1 for row in rows if row["intent_family"] == "clarification_required")
    print(f"clarification_required total: {clarification_total} (baseline {CLARIFICATION_BASELINE})")

    violations = errors + check_rows(rows)
    if args.json:
        args.json.write_text(
            json.dumps({"rows": rows, "violations": violations}, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {args.json}")

    if violations:
        print(f"\nVIOLATIONS ({len(violations)}):")
        for item in violations:
            print(f"  - {item}")
        return 1 if args.check else 0
    print("\nall gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
