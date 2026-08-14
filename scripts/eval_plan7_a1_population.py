#!/usr/bin/env python3
"""Plan 7 A1 — structural population sweep for lost mandatory lifecycle work.

Runs each corpus query through the **production** runtime — the resource-planner
graph (`run_chat_via_resource_planner_graph`), the same entrypoint `/chat` uses,
not the imperative re-run — with the remediation
posture forced (ResourcePlan execution ON, dispatch-v2 OFF) and **instruments the
merge seam** rather than guessing from answers: `merge_schedule` is wrapped so
every call records the resolved PhaseContract, the compiler verdict and the merge
result for that turn.

Classification is by **mechanism and phase type**, never by query ID.

    python3 scripts/eval_plan7_a1_population.py --corpus all --out docs/evals/plan7/a1_structural_population.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "backend", ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

# Offline structural audit, not a provider-availability test. Advisory/live
# components off so local flags cannot add network noise to the sweep.
os.environ["AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED"] = "false"
os.environ["AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED"] = "false"
os.environ["AI_SOC_LLM_EVIDENCE_OBSERVER_ENABLED"] = "false"
os.environ["AI_SOC_LLM_SPL_FALLBACK_ENABLED"] = "false"
os.environ["AI_SOC_LLM_UTILITY_SPL_DRAFT_ENABLED"] = "false"

from app.config import settings  # noqa: E402

for _name in (
    "ai_soc_llm_enabled",
    "ai_soc_llm_intent_advisor_enabled",
    "ai_soc_llm_spl_fallback_enabled",
    "ai_soc_llm_utility_spl_draft_enabled",
    "ai_soc_llm_final_synthesis_enabled",
    "ai_soc_llm_live_synthesis_enabled",
):
    if hasattr(settings, _name):
        setattr(settings, _name, False)

# The remediation posture under audit. T4 is left exactly as the runtime has it —
# this script never turns T4 off.
settings.ai_soc_resource_plan_execution_enabled = True
settings.ai_soc_pipeline_dispatch_v2_enabled = False

from app.graph.resource_planner_graph import (  # noqa: E402
    run_chat_via_resource_planner_graph,
)
from app.planner import phase_schedule_merge as merge_mod  # noqa: E402
from app.planner import executor as executor_mod  # noqa: E402
from app.schemas.requests import ChatRequest  # noqa: E402

_RECORDS: list[dict[str, Any]] = []
_real_merge = merge_mod.merge_schedule


def _instrumented_merge(contract, plan, phase_contract, inputs):
    """Record what the run owed and what the merge did with it."""
    from app.planner.resource_plan_execution_scheduler import compile_execution_schedule

    compiled, compile_downgrade = compile_execution_schedule(plan, inputs)
    merged, reason = _real_merge(contract, plan, phase_contract, inputs)

    mandatory = sorted(p.name for p in phase_contract.phases if p.mandatory)
    applicable = sorted(p.name for p in phase_contract.phases)
    represented: set[str] = set()
    if merged is not None:
        represented = set(merged.hooks) | set(merged.inline_phases)

    _RECORDS.append(
        {
            "compile_downgrade": compile_downgrade,
            "compiled_hooks": list(compiled.hooks) if compiled is not None else None,
            "merge_reason": reason,
            "merged": merged is not None,
            "merged_hooks": list(merged.hooks) if merged is not None else None,
            "phase_contract_applicable": applicable,
            "phase_contract_mandatory": mandatory,
            "mandatory_lost": sorted(set(mandatory) - represented) if merged is None else sorted(
                set(mandatory) - represented
            ),
            "intent_family": getattr(contract, "intent_family", None),
            "answer_goal": getattr(contract, "answer_goal", None),
            "qualification_tier": getattr(contract, "qualification_tier", None),
        }
    )
    return merged, reason


merge_mod.merge_schedule = _instrumented_merge
if hasattr(executor_mod, "merge_schedule"):  # imported lazily inside the executor
    executor_mod.merge_schedule = _instrumented_merge

_SEAM: list[dict[str, Any]] = []
_real_detailed = executor_mod._execution_driven_schedule_detailed


def _instrumented_detailed(state, walk):
    """Record whether the execution-authority seam was reached at all."""
    compiled, reason, trace = _real_detailed(state, walk)
    _SEAM.append(
        {
            "compiled": compiled is not None,
            "downgrade_reason": reason,
            "had_contract": bool(state.get("resolved_query_contract")),
            "had_plan": bool(
                (state.get("evidence_plan") or {}).get("resource_plan")
                if isinstance(state.get("evidence_plan"), dict)
                else False
            ),
        }
    )
    return compiled, reason, trace


executor_mod._execution_driven_schedule_detailed = _instrumented_detailed


def _load_corpus(name: str) -> list[tuple[str, str, str]]:
    """(corpus, row_id, query) triples."""
    rows: list[tuple[str, str, str]] = []
    if name in {"plan6", "all"}:
        payload = json.loads(
            (ROOT / "docs" / "evals" / "plan6" / "vps_corpus_v1.json").read_text("utf-8")
        )
        for row in payload["rows"] if isinstance(payload, dict) else payload:
            rows.append(("plan6_corpus", str(row["row_id"]), str(row["query"])))
    if name in {"golden105", "all"}:
        path = ROOT / "backend" / "app" / "evals" / "golden_answers" / "question_105_golden.jsonl"
        for line in path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            query = row.get("question") or row.get("query") or row.get("prompt")
            if query:
                rows.append(("golden_105", str(row.get("question_id") or row.get("id")), str(query)))
    if name in {"cisco50", "all"}:
        payload = json.loads(
            (ROOT / "docs" / "evals" / "cisco_powergrid_question_bank.json").read_text("utf-8")
        )
        entries = payload["questions"] if isinstance(payload, dict) else payload
        for row in entries:
            query = row.get("question") or row.get("query")
            if query:
                rows.append(("cisco_50", str(row.get("id") or row.get("question_id")), str(query)))
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
        _RECORDS.clear()
        _SEAM.clear()
        started = time.monotonic()
        error = None
        try:
            run_chat_via_resource_planner_graph(ChatRequest(message=query))
        except Exception as exc:  # noqa: BLE001 - a failing row is data, not a crash
            error = f"{type(exc).__name__}: {exc}"[:200]
        results.append(
            {
                "corpus": corpus,
                "row_id": row_id,
                "wall_ms": int((time.monotonic() - started) * 1000),
                "error": error,
                "merge_calls": list(_RECORDS),
                "seam_calls": list(_SEAM),
            }
        )
        print(
            json.dumps(
                {
                    "corpus": corpus,
                    "row_id": row_id,
                    "seam_calls": len(_SEAM),
                    "seam_reasons": [s["downgrade_reason"] for s in _SEAM],
                    "merge_calls": len(_RECORDS),
                    "downgrades": [r["compile_downgrade"] for r in _RECORDS],
                    "lost": [r["mandatory_lost"] for r in _RECORDS],
                }
            ),
            flush=True,
        )

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "rows": len(results), "out": str(out.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
