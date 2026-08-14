#!/usr/bin/env python3
"""Plan 6 B2 — redacted A/B/C comparison from stored VPS traces.

Does not re-run /chat. Fetches existing /debug bundles. No SPL text, no secrets.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FETCH = REPO_ROOT / "scripts" / "fetch_debug_bundle.sh"
RUNS = REPO_ROOT / "docs" / "evals" / "plan6" / "runs"
OUT = REPO_ROOT / "docs" / "evals" / "plan6" / "execution_off_on_comparison.json"

ARMS = {
    "A": RUNS / "20260813T114521Z" / "summary.json",
    "B": RUNS / "20260813T122303Z" / "summary.json",
    "C": RUNS / "20260813T125517Z" / "summary.json",
}

CORPUS_ORDER = (
    "p6.t1.knowledge",
    "p6.t2.known_nontrivial",
    "p6.t4.out_of_registry",
    "p6.spl.draft",
    "p6.spl.mcp",
    "p6.multi.knowledge_spl_mcp",
    "p6.clarify",
    "p6.unsafe",
    "p6.alert.summary",
    "p6.live_posture.d1_003",
    "p6.repeat.refinement",
    "p6.fail.degraded",
)


def _fetch(trace_id: str) -> dict[str, Any] | None:
    proc = subprocess.run(
        [str(FETCH), trace_id],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    text = (proc.stdout or "").strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _slice(summary_row: dict[str, Any], bundle: dict[str, Any] | None) -> dict[str, Any]:
    chat = summary_row.get("chat") if isinstance(summary_row.get("chat"), dict) else {}
    fields = (
        summary_row.get("debug_summary_fields")
        if isinstance(summary_row.get("debug_summary_fields"), dict)
        else {}
    )
    explain = bundle.get("explainability") if isinstance(bundle, dict) else None
    ds = explain.get("debug_summary") if isinstance(explain, dict) else None
    ds = ds if isinstance(ds, dict) else {}
    routing = ds.get("routing") if isinstance(ds.get("routing"), dict) else {}
    resolved = ds.get("resolved_query") if isinstance(ds.get("resolved_query"), dict) else {}
    schedule = ds.get("schedule") if isinstance(ds.get("schedule"), dict) else {}
    spl = ds.get("spl") if isinstance(ds.get("spl"), dict) else {}
    mcp = ds.get("mcp") if isinstance(ds.get("mcp"), dict) else {}
    hil = ds.get("hil") if isinstance(ds.get("hil"), dict) else {}
    llm = ds.get("llm") if isinstance(ds.get("llm"), dict) else {}
    dispatch = ds.get("dispatch") if isinstance(ds.get("dispatch"), dict) else {}
    output = ds.get("output") if isinstance(ds.get("output"), dict) else {}
    payload = bundle.get("payload") if isinstance(bundle, dict) else None
    payload = payload if isinstance(payload, dict) else {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    human_review = (
        payload.get("human_review") if isinstance(payload.get("human_review"), dict) else {}
    )
    live_roles = llm.get("live_roles") if isinstance(llm.get("live_roles"), list) else []
    dispatch_schedule = schedule.get("dispatch_schedule")
    dispatch_schedule = list(dispatch_schedule) if isinstance(dispatch_schedule, list) else []
    phase_names = schedule.get("phase_names")
    phase_names = list(phase_names) if isinstance(phase_names, list) else list(
        fields.get("phase_names") or []
    )
    executed = schedule.get("executed_hooks")
    executed = list(executed) if isinstance(executed, list) else []
    stage_schedule = dispatch.get("stage_schedule")
    stage_schedule = list(stage_schedule) if isinstance(stage_schedule, list) else []
    llm_hops = dispatch.get("llm_hops")
    llm_hops = list(llm_hops) if isinstance(llm_hops, list) else []
    caps_req = resolved.get("required_capabilities")
    caps_proh = resolved.get("prohibited_capabilities")
    execution_eligible = execution.get("execution_eligible")
    if execution_eligible is None:
        execution_eligible = payload.get("execution_eligible")
    return {
        "trace_id": summary_row.get("trace_id"),
        "bundle_present": bool(ds),
        "route": chat.get("route") or routing.get("skill") or routing.get("selected_skill"),
        "answer_mode": chat.get("answer_mode"),
        "execution_enabled": chat.get("execution_enabled"),
        "execution_eligible": execution_eligible,
        "qualification_tier": resolved.get("qualification_tier") or fields.get("qualification_tier"),
        "intent_family": resolved.get("intent_family") or fields.get("intent_family"),
        "answer_goal": resolved.get("answer_goal") or fields.get("answer_goal"),
        "ambiguity_state": resolved.get("ambiguity_state") or fields.get("ambiguity_state"),
        "clarification_required": resolved.get("clarification_required"),
        "required_capabilities": list(caps_req) if isinstance(caps_req, list) else [],
        "prohibited_capabilities": list(caps_proh) if isinstance(caps_proh, list) else [],
        "match_path": routing.get("match_path"),
        "resource_plan_fingerprint": schedule.get("resource_plan_fingerprint")
        or fields.get("resource_plan_fingerprint"),
        "degrade_reason": schedule.get("degrade_reason")
        if schedule.get("degrade_reason") is not None
        else fields.get("degrade_reason"),
        "dispatch_schedule": dispatch_schedule,
        "phase_names": phase_names,
        "executed_hooks": executed,
        "stage_schedule": stage_schedule,
        "spl_approved": spl.get("approved"),
        "spl_normalized_present": spl.get("normalized_spl"),
        "spl_reject_reasons": list(spl.get("reject_reasons") or [])[:6],
        "spl_path": llm.get("spl_path"),
        "mcp_allowed": mcp.get("allowed"),
        "mcp_status": mcp.get("status"),
        "mcp_block_reason": mcp.get("block_reason"),
        "hil_required": hil.get("required") if hil else human_review.get("required"),
        "hil_kind": hil.get("kind") or human_review.get("review_type"),
        "hil_reason": hil.get("reason"),
        "rbac_decision": schedule.get("rbac_decision"),
        "session_role": schedule.get("session_role"),
        "live_llm_roles": [str(item) for item in live_roles][:8],
        "live_llm_count": len(live_roles),
        "dispatch_llm_hops": [str(item) for item in llm_hops][:8],
        "output_answer_mode": output.get("answer_mode"),
        "grounding_present": bool(output.get("grounding") or payload.get("grounding")),
        "second_engine": bool(schedule.get("degrade_reason") == "fallback")
        or "legacy" in str(dispatch.get("dispatch_cursor") or ""),
    }


def _path_class(row: dict[str, Any], arm: str) -> str:
    reason = row.get("degrade_reason")
    mode = row.get("answer_mode")
    if arm == "A":
        if mode == "rag_only":
            return "exec_off:rag_only_path"
        if mode == "clarification":
            return "exec_off:non_planned"
        return "exec_off:composed_zero_merge_code"
    if arm == "B":
        if reason == "dispatch_v2_projected_schedule":
            return "v2_wins_merge_stood_down"
        if mode == "rag_only":
            return "merge_not_reachable:rag_only"
        if mode == "clarification":
            return "merge_not_reachable:non_planned"
        return f"other:{reason}"
    if reason == "merge":
        return "merge_executed"
    if reason == "no_schedulable_step":
        return "merge_not_reachable:no_schedulable_step"
    if mode == "rag_only":
        return "merge_not_reachable:rag_only"
    if mode == "clarification":
        return "merge_not_reachable:non_planned"
    return f"other:{reason}"


def main() -> int:
    by_arm: dict[str, dict[str, Any]] = {}
    for arm, path in ARMS.items():
        summary = json.loads(path.read_text(encoding="utf-8"))
        rows = {str(item["row_id"]): item for item in summary["results"]}
        by_arm[arm] = rows

    comparison: dict[str, Any] = {
        "schema_version": "plan6_b2_execution_off_on_v1",
        "git_sha": "1d32ac66dd6c707789db8b44574bd566af401952",
        "surface": "LOCAL comparison of stored VPS traces (no re-run)",
        "corpus_rows": list(CORPUS_ORDER),
        "paraphrase_rows": "n/a — Arm D only; not in A/B/C corpus",
        "rows": {},
    }
    for row_id in CORPUS_ORDER:
        cells: dict[str, Any] = {}
        for arm in ("A", "B", "C"):
            raw = by_arm[arm][row_id]
            bundle = _fetch(str(raw.get("trace_id") or "")) if raw.get("trace_id") else None
            sliced = _slice(raw, bundle)
            sliced["path_class"] = _path_class(sliced, arm)
            cells[arm] = sliced
            print(f"{arm} {row_id} bundle={sliced['bundle_present']} path={sliced['path_class']}", flush=True)
        comparison["rows"][row_id] = {
            "class": by_arm["A"][row_id].get("class"),
            "arms": cells,
        }
    OUT.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
