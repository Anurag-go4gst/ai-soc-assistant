#!/usr/bin/env python3
"""Item 2 dump: coverage/margin distribution on the live matcher.

Reads the instrumented production bind (`match_use_cases`) — confidence still
decides; diagnostics are reported only. Classifies truth-set rows into correct
binds vs misfires so item 3 can see whether any univariate statistic separates
them. Also dumps the T2-binding subset of the 105 (most 105 rows never bind
at T2) and a catalogue inventory for the templateless cull.

Run:
  cd backend && PYTHONPATH=../backend:.. python3 ../scripts/eval_catalogue_bind_distribution.py
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

from app.coverage.question_runtime_map import list_question_runtime_entries
from app.use_cases.registry import load_use_case_catalog, match_use_cases

KNOWLEDGE_SKILLS = {
    "knowledge_recall",
    "mitre_mapping",
    "investigation_notes",
    "ticket_drafting",
    "action_planning",
}
HUNT_SKILLS = {"attack_discovery", "spl_generation", "alert_summary"}


def _bind(query: str):
    matches = match_use_cases(query, limit=3)
    return matches[0] if matches else None


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "min": round(ordered[0], 4),
        "p25": round(ordered[len(ordered) // 4], 4),
        "median": round(statistics.median(ordered), 4),
        "p75": round(ordered[(len(ordered) * 3) // 4], 4),
        "max": round(ordered[-1], 4),
        "mean": round(statistics.mean(ordered), 4),
    }


def _overlap(a: list[float], b: list[float]) -> dict:
    if not a or not b:
        return {"separates": False, "reason": "empty population"}
    a_min, a_max = min(a), max(a)
    b_min, b_max = min(b), max(b)
    separates = a_max < b_min or b_max < a_min
    return {
        "separates": separates,
        "correct_range": [round(a_min, 4), round(a_max, 4)],
        "misfire_range": [round(b_min, 4), round(b_max, 4)],
        "gap": round(min(a_min - b_max, b_min - a_max), 4) if separates else None,
    }


def classify_truth_row(row: dict, top) -> str:
    """Bind-level class, not the final route.

    correct_bind     bound use case's skill is in acceptable_skills
    false_knowledge  label requires SPL, bind is a knowledge/meta skill
    missed_procedure label forbids SPL, no knowledge bind (no-bind or hunt bind)
    no_bind          nothing bound; not a missed-procedure case
    wrong_family     bound a hunt/other skill outside acceptable_skills
    """
    req_spl = "spl" in (row.get("required_capabilities") or [])
    forb_spl = "spl" in (row.get("forbidden_capabilities") or [])
    acceptable = set(row.get("acceptable_skills") or [])
    if top is None:
        if forb_spl:
            return "missed_procedure"
        return "no_bind"
    skill = top.primary_skill
    if skill in acceptable:
        return "correct_bind"
    if req_spl and skill in KNOWLEDGE_SKILLS:
        return "false_knowledge"
    if forb_spl and skill not in KNOWLEDGE_SKILLS:
        return "missed_procedure"
    return "wrong_family"


def main() -> None:
    truth = json.loads((REPO / "docs/evals/routing_truth_set_v1.json").read_text())["rows"]
    catalogue = load_use_case_catalog()
    by_id = {u.use_case_id: u for u in catalogue}

    truth_rows = []
    for row in truth:
        top = _bind(row["query"])
        klass = classify_truth_row(row, top)
        truth_rows.append(
            {
                "row_id": row["row_id"],
                "class": klass,
                "required_spl": "spl" in (row.get("required_capabilities") or []),
                "forbidden_spl": "spl" in (row.get("forbidden_capabilities") or []),
                "acceptable_skills": list(row.get("acceptable_skills") or []),
                "use_case_id": None if top is None else top.use_case_id,
                "primary_skill": None if top is None else top.primary_skill,
                "matched_patterns": [] if top is None else list(top.matched_patterns),
                "confidence": None if top is None else top.confidence,
                "coverage_ratio": None if top is None else top.coverage_ratio,
                "specificity": None if top is None else top.specificity,
                "coverage_score": None if top is None else top.coverage_score,
                "runner_up_score": None if top is None else top.runner_up_score,
                "bind_margin": None if top is None else top.bind_margin,
                "has_spl_template": None
                if top is None
                else bool(by_id[top.use_case_id].default_spl_template),
            }
        )

    q105 = []
    for entry in list_question_runtime_entries():
        text = entry.get("question") or entry.get("query")
        if not text:
            continue
        top = _bind(text)
        q105.append(
            {
                "question_ref": entry.get("question_ref"),
                "binds": top is not None,
                "use_case_id": None if top is None else top.use_case_id,
                "primary_skill": None if top is None else top.primary_skill,
                "matched_patterns": [] if top is None else list(top.matched_patterns),
                "coverage_ratio": None if top is None else top.coverage_ratio,
                "specificity": None if top is None else top.specificity,
                "coverage_score": None if top is None else top.coverage_score,
                "runner_up_score": None if top is None else top.runner_up_score,
                "bind_margin": None if top is None else top.bind_margin,
                "has_spl_template": None
                if top is None
                else bool(by_id[top.use_case_id].default_spl_template),
            }
        )

    bound_truth = [r for r in truth_rows if r["coverage_score"] is not None]
    correct = [r for r in bound_truth if r["class"] == "correct_bind"]
    misfire = [r for r in bound_truth if r["class"] in {"false_knowledge", "wrong_family", "missed_procedure"}]
    false_k = [r for r in bound_truth if r["class"] == "false_knowledge"]

    metrics = ("coverage_ratio", "specificity", "coverage_score", "bind_margin")
    population_stats = {}
    overlap = {}
    for metric in metrics:
        c_vals = [r[metric] for r in correct if r[metric] is not None]
        m_vals = [r[metric] for r in misfire if r[metric] is not None]
        fk_vals = [r[metric] for r in false_k if r[metric] is not None]
        population_stats[metric] = {
            "correct_bind": _stats(c_vals),
            "misfire": _stats(m_vals),
            "false_knowledge": _stats(fk_vals),
        }
        overlap[metric] = {
            "correct_vs_misfire": _overlap(c_vals, m_vals),
            "correct_vs_false_knowledge": _overlap(c_vals, fk_vals),
        }

    class_counts = Counter(r["class"] for r in truth_rows)
    bound_105 = [r for r in q105 if r["binds"]]
    margins = [r["bind_margin"] for r in bound_truth if r["bind_margin"] is not None]
    contested = sum(1 for m in margins if abs(m) < 0.12)
    negative_margin = sum(1 for m in margins if m < 0)

    inventory = []
    for u in catalogue:
        mcp = any(str(s).startswith("mcp:") for s in (u.required_sources or []))
        inventory.append(
            {
                "use_case_id": u.use_case_id,
                "display_name": u.display_name,
                "primary_skill": u.primary_skill,
                "use_case_type": u.use_case_type,
                "bindable": bool(u.intent_patterns),
                "has_spl_template": bool(u.default_spl_template),
                "default_spl_template": u.default_spl_template,
                "requires_mcp": mcp,
                "required_sources": list(u.required_sources or []),
                "rag_collections": list(u.rag_collections or []),
                "intent_patterns": list(u.intent_patterns or []),
                "registry_tier": u.registry_tier,
            }
        )

    templateless_bindable = [
        u for u in inventory if u["bindable"] and not u["has_spl_template"]
    ]

    payload = {
        "schema_version": "catalogue_bind_distribution_v1",
        "plan": "plans/2026-08-19_1130_catalogue-matching-coverage-and-margin.md",
        "item": 2,
        "matcher": "production match_use_cases; confidence still decides",
        "counts": {
            "truth_set_rows": len(truth_rows),
            "truth_set_bound": len(bound_truth),
            "truth_set_unbound": len(truth_rows) - len(bound_truth),
            "class_counts": dict(class_counts),
            "questions_105": len(q105),
            "questions_105_binding_at_t2": len(bound_105),
            "questions_105_unbound_at_t2": len(q105) - len(bound_105),
            "bind_margin_observed": len(margins),
            "bind_margin_abs_lt_0_12": contested,
            "bind_margin_negative": negative_margin,
            "catalogue": len(inventory),
            "bindable": sum(1 for u in inventory if u["bindable"]),
            "bindable_without_template": len(templateless_bindable),
        },
        "population_stats": population_stats,
        "overlap": overlap,
        "univariate_separates": {
            metric: overlap[metric]["correct_vs_misfire"]["separates"]
            or overlap[metric]["correct_vs_false_knowledge"]["separates"]
            for metric in metrics
        },
        "truth_set_rows": truth_rows,
        "questions_105_binding": bound_105,
        "catalogue_inventory": inventory,
        "templateless_bindable": templateless_bindable,
    }

    out = REPO / "docs/evals/catalogue_bind_distribution_v1.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out}")
    print("counts:", json.dumps(payload["counts"], indent=2))
    print("overlap:", json.dumps(payload["overlap"], indent=2))
    print("univariate_separates:", json.dumps(payload["univariate_separates"], indent=2))
    print("class_counts:", dict(class_counts))
    print("\nfalse_knowledge rows:")
    for r in truth_rows:
        if r["class"] == "false_knowledge":
            print(f"  {r['row_id']:16} {r['use_case_id']:32} cov={r['coverage_ratio']} spec={r['specificity']} score={r['coverage_score']} margin={r['bind_margin']} matched={r['matched_patterns']}")
    print("\nwrong_family rows:")
    for r in truth_rows:
        if r["class"] == "wrong_family":
            print(f"  {r['row_id']:16} {r['use_case_id']:32} skill={r['primary_skill']} cov={r['coverage_ratio']} score={r['coverage_score']} matched={r['matched_patterns']}")
    print("\ncorrect_bind with coverage_ratio <= 0.20:")
    for r in correct:
        if (r["coverage_ratio"] or 1) <= 0.20:
            print(f"  {r['row_id']:16} {r['use_case_id']:32} cov={r['coverage_ratio']} spec={r['specificity']} score={r['coverage_score']} matched={r['matched_patterns']}")
    print("\ntemplateless bindable:")
    for u in templateless_bindable:
        kind = "knowledge_no_mcp" if (u["primary_skill"] in KNOWLEDGE_SKILLS and not u["requires_mcp"]) else "delete_candidate"
        print(f"  {u['use_case_id']:42} skill={u['primary_skill']:22} mcp={str(u['requires_mcp']):5} type={u['use_case_type'] or '-':22} {kind}")


if __name__ == "__main__":
    main()
