#!/usr/bin/env python3
"""Publish OPTIONAL_PHASE_S S1 classification distribution (per producer × flag).

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_spl_optimization_s1_distribution.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "docs/evals/spl_optimization/authority_baseline_v1.json"
OUT = ROOT / "docs/evals/spl_optimization/s1_classification_distribution_v1.json"


def _stable(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def main() -> int:
    from app.spl.draft_quality import evaluate_draft_quality

    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    # Classification is deterministic on candidate text; flag state does not change
    # the detector. Report both flag postures so a pooled zero cannot be misread
    # after the compiler becomes correct-by-construction (P12).
    by_flag: dict[str, Any] = {}
    for flag_state in (False, True):
        per_path: dict[str, Counter[str]] = defaultdict(Counter)
        per_path_rules: dict[str, Counter[str]] = defaultdict(Counter)
        for row in freeze["rows"]:
            if row["bank"] != "spl_golden" or not row.get("candidate_spl"):
                continue
            path = row.get("producer_path") or "unknown"
            # Free-text path is only live when fallback flag is true; still classify
            # template/compiler rows under both postures for incidence evidence.
            if path == "llm_fallback" and not flag_state:
                continue
            report = evaluate_draft_quality(row["candidate_spl"])
            per_path[path][report.optimization_classification] += 1
            for item in report.findings:
                if item.severity == "advisory" and item.rule_id.endswith(
                    ("Q03", "Q04", "Q15", "Q16", "Q17", "Q18")
                ):
                    per_path_rules[path][item.rule_id.split("-")[-1]] += 1
        by_flag[f"ai_soc_llm_spl_fallback_enabled={flag_state}"] = {
            "by_producer_path": {
                path: dict(counter) for path, counter in sorted(per_path.items())
            },
            "efficiency_advisory_hits": {
                path: dict(counter) for path, counter in sorted(per_path_rules.items())
            },
        }

    # Convergence SPL pins — no candidate text; record structural posture only.
    convergence_spl = [
        r for r in freeze["rows"] if r["bank"] == "convergence" and str(r["row_id"]).startswith("CV.SPL")
    ]

    artifact = {
        "artifact_id": "s1_classification_distribution_v1",
        "base_sha": freeze.get("base_sha"),
        "note": (
            "Distribution is evidence for Layer-3 trigger frequency / bank coverage — "
            "not a gate to delete Layer 3. Split by producer_path and "
            "ai_soc_llm_spl_fallback_enabled (P12)."
        ),
        "convergence_spl_rows": [
            {
                "row_id": r["row_id"],
                "execution_eligible": r["execution_eligible"],
                "approved": r["approved"],
                "normalized_spl": r["normalized_spl"],
            }
            for r in convergence_spl
        ],
        "distributions": by_flag,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(_stable(artifact), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(json.dumps(by_flag, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
