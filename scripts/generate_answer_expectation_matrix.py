#!/usr/bin/env python3
"""Generate answer expectation matrix and draft golden JSONL rows (Phase 0 + 6)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = REPO_ROOT / "backend/app/coverage/question_runtime_map_v1.json"
CATALOG_PATH = REPO_ROOT / "backend/app/use_cases/catalog.json"
OUT_DIR = REPO_ROOT / "docs/evals/out"
GOLDEN_DIR = REPO_ROOT / "backend/app/evals/golden_answers"
FIXTURE_PATH = REPO_ROOT / "backend/app/evals/fixtures/control_plane_critical_flows.jsonl"

SKILL_COLLAPSE = {
    "spl_generation",
    "spl_validation",
    "evidence_collection",
    "context_sufficiency",
    "mitre_mapping",
    "action_planning",
    "sequence_detection",
    "notable_risk_lookup",
}


def _outcome_for_question(entry: dict[str, Any]) -> tuple[str, bool, str]:
    question = (entry.get("question") or "").lower()
    skill = entry.get("proposed_primary_skill") or entry.get("legacy_router_intent_hint") or ""
    dep = entry.get("dependency_class") or ""
    if entry.get("route_blocked"):
        return "unsupported", False, "route_blocked_on_runtime_map"
    if dep in {"notable_risk_source", "external_threat_intel", "unavailable_source"}:
        return "source_unavailable", False, f"dependency_class:{dep}"
    if "mitre" in question and not any(token in question for token in ("alert", "notable", "alt-", "incident id")):
        return "clarification", False, "mitre_without_alert_context"
    if skill in {"knowledge_recall", "sop_or_playbook"} or "policy" in question or "playbook" in question or "sop" in question:
        return "rag_policy", skill == "knowledge_recall", "policy_or_playbook_intent"
    if "mitre" in question:
        return "mitre_mapping", False, "mitre_with_context_or_hybrid"
    if skill in {"spl_generation", "attack_discovery"} or "spl" in question:
        return "spl_candidate", False, "investigation_or_spl_generation"
    return "answer", False, "default_investigation"


def _outcome_for_use_case(row: dict[str, Any]) -> tuple[str, bool, str]:
    skill = row.get("primary_skill") or ""
    if skill in SKILL_COLLAPSE:
        route_skill = "knowledge_recall"
    else:
        route_skill = skill
    patterns = " ".join(row.get("intent_patterns") or []).lower()
    if "mitre" in patterns:
        return "mitre_mapping", False, "catalog_mitre_intent"
    if skill in {"knowledge_recall", "sop_or_playbook"} or "policy" in patterns or "playbook" in patterns:
        return "rag_policy", True, "catalog_policy_or_knowledge"
    if route_skill == "knowledge_recall":
        return "clarification", False, "non_enum_skill_collapsed"
    return "spl_candidate", False, "catalog_investigation_default"


def _golden_row_shallow(
    *,
    case_id: str,
    tier: int,
    source: str,
    query: str,
    category: str,
    expected: dict[str, Any],
    tags: list[str],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "tier": tier,
        "source": source,
        "query": query,
        "category": category,
        "tags": tags,
        "expected": expected,
        "notes": "Auto-generated shallow expectation; deepen when matrix marks deep_assertion_eligible.",
    }


def main() -> int:
    map_data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []

    for entry in map_data.get("entries") or []:
        ref = entry.get("question_ref") or f"q{entry.get('question_number')}"
        category, deep, reason = _outcome_for_question(entry)
        skill = entry.get("proposed_primary_skill") or entry.get("legacy_router_intent_hint")
        rows.append(
            {
                "row_id": ref,
                "row_kind": "question_105",
                "display_name": entry.get("question"),
                "expected_outcome_category": category,
                "dependency_class": entry.get("dependency_class"),
                "deep_assertion_eligible": deep,
                "deep_assertion_reason": reason if not deep else "",
                "proposed_primary_skill": skill,
            }
        )

    for item in catalog.get("use_cases") or []:
        uid = item.get("use_case_id")
        category, deep, reason = _outcome_for_use_case(item)
        skill = item.get("primary_skill")
        route_skill = "knowledge_recall" if skill in SKILL_COLLAPSE else skill
        rows.append(
            {
                "row_id": uid,
                "row_kind": "use_case_catalog",
                "display_name": item.get("display_name"),
                "expected_outcome_category": category,
                "dependency_class": "catalog_row",
                "deep_assertion_eligible": deep,
                "deep_assertion_reason": reason if not deep else "",
                "proposed_primary_skill": skill,
                "expected_selected_skill": route_skill,
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix_path = OUT_DIR / "answer_expectation_matrix.json"
    matrix_path.write_text(json.dumps({"generated_from": [str(MAP_PATH), str(CATALOG_PATH)], "rows": rows}, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# Answer Expectation Matrix",
        "",
        f"Rows: {len(rows)} (105 questions + {len(catalog.get('use_cases') or [])} catalog use cases)",
        "",
        "| row_id | kind | outcome | deep | skill |",
        "|---|---|---|:---:|---|",
    ]
    for row in rows[:40]:
        md_lines.append(
            f"| `{row['row_id']}` | {row['row_kind']} | {row['expected_outcome_category']} | "
            f"{'yes' if row['deep_assertion_eligible'] else 'no'} | {row.get('proposed_primary_skill') or ''} |"
        )
    if len(rows) > 40:
        md_lines.append(f"\n… and {len(rows) - 40} more rows in `answer_expectation_matrix.json`.")
    (OUT_DIR / "answer_expectation_matrix.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

  # Shallow golden JSONL (tier 2)
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    q_cases: list[dict[str, Any]] = []
    for row in rows:
        if row["row_kind"] != "question_105":
            continue
        expected: dict[str, Any] = {}
        if row.get("proposed_primary_skill"):
            expected["selected_skill"] = (
                "knowledge_recall"
                if row["proposed_primary_skill"] in SKILL_COLLAPSE
                else row["proposed_primary_skill"]
            )
        if row["expected_outcome_category"] in {"rag_policy", "clarification"}:
            expected["answer_mode"] = row["expected_outcome_category"]
        q_cases.append(
            _golden_row_shallow(
                case_id=f"q105.{row['row_id']}",
                tier=2,
                source="question_runtime_map",
                query=row["display_name"] or row["row_id"],
                category=row["expected_outcome_category"],
                expected=expected,
                tags=["auto_matrix", "tier2", "shallow"],
            )
        )

    c_cases: list[dict[str, Any]] = []
    for row in rows:
        if row["row_kind"] != "use_case_catalog":
            continue
        expected = {
            "selected_use_case_id": row["row_id"],
            "selected_skill": row.get("expected_selected_skill"),
        }
        c_cases.append(
            _golden_row_shallow(
                case_id=f"catalog.{row['row_id']}",
                tier=2,
                source="use_case_catalog",
                query=row["display_name"] or row["row_id"],
                category=row["expected_outcome_category"],
                expected=expected,
                tags=["auto_matrix", "tier2", "shallow"],
            )
        )

    def write_jsonl(path: Path, cases: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for case in cases:
                handle.write(json.dumps(case, sort_keys=True) + "\n")

    write_jsonl(GOLDEN_DIR / "question_105_golden.jsonl", q_cases)
    write_jsonl(GOLDEN_DIR / "use_case_catalog_golden.jsonl", c_cases)

    tier0_src = GOLDEN_DIR / "tier0_control_plane.jsonl"
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if tier0_src.is_file():
        FIXTURE_PATH.write_text(tier0_src.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"wrote {matrix_path} ({len(rows)} rows)")
    print(f"wrote {GOLDEN_DIR / 'question_105_golden.jsonl'} ({len(q_cases)} cases)")
    print(f"wrote {GOLDEN_DIR / 'use_case_catalog_golden.jsonl'} ({len(c_cases)} cases)")
    if FIXTURE_PATH.is_file():
        print(f"wrote {FIXTURE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
