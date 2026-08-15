#!/usr/bin/env python3
"""Audit current ResourcePlan routing for the reference-knowledge probe contract.

Default mode is ``--check``: run the ten probes, compare them against the frozen
baseline, and **write nothing**. A verification gate must never rewrite the
artifact it is verifying — before this had a CLI, every run overwrote
``docs/evals/reference_knowledge_baseline.md``, so "the probes pass" was
unfalsifiable and drift landed silently in commits.

    python3 scripts/audit_reference_probes.py --check                # gate (default)
    python3 scripts/audit_reference_probes.py --out /tmp/probes.md   # scratch report
    python3 scripts/audit_reference_probes.py --update-baseline      # deliberate refresh

Exit codes: 0 = matches baseline, 1 = drift, 2 = usage/IO error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "backend", ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

# This is an offline routing/reference contract audit, not a provider availability
# test. Force advisory/live components off so local environment flags cannot add
# network noise or change the frozen route rows.
os.environ["AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED"] = "false"
os.environ["AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED"] = "false"
os.environ["AI_SOC_LLM_EVIDENCE_OBSERVER_ENABLED"] = "false"
os.environ["AI_SOC_LLM_SPL_FALLBACK_ENABLED"] = "false"
os.environ["AI_SOC_LLM_UTILITY_SPL_DRAFT_ENABLED"] = "false"
os.environ["MCP_GLOBAL_EXECUTION_ENABLED"] = "false"

from app.chat.pipeline import build_live_chat_response  # noqa: E402
from app.chat.answer_shape_router import classify_answer_shape  # noqa: E402
from app.chat.debug_summary import build_debug_summary  # noqa: E402
from app.config import settings  # noqa: E402
from app.schemas.requests import ChatRequest  # noqa: E402

for _setting_name in (
    "ai_soc_llm_enabled",
    "ai_soc_llm_intent_advisor_enabled",
    "ai_soc_llm_spl_fallback_enabled",
    "ai_soc_llm_utility_spl_draft_enabled",
    "ai_soc_llm_final_synthesis_enabled",
    "ai_soc_llm_live_synthesis_enabled",
    "mcp_global_execution_enabled",
):
    if hasattr(settings, _setting_name):
        setattr(settings, _setting_name, False)

# This is the Plan 7 authority probe, not a rollback compatibility probe.  Pin
# only the two execution-authority switches so the result cannot silently fall
# back to dispatch-v2 because of a developer shell or stale local profile.
settings.ai_soc_resource_plan_execution_enabled = True
settings.ai_soc_pipeline_dispatch_v2_enabled = False
settings.ai_soc_t4_semantic_understanding_enabled = False

PROBES = ROOT / "backend" / "app" / "tests" / "fixtures" / "reference_knowledge" / "probes.json"
OUT = ROOT / "docs" / "evals" / "reference_knowledge_baseline.md"
ROW_TIMEOUT_SECONDS = 20


class RowTimeout(RuntimeError):
    pass


def _raise_timeout(_signum: int, _frame: object) -> None:
    raise RowTimeout("row_timeout")


def _dig(payload: dict[str, Any], *keys: str) -> Any:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _route_row(probe: dict[str, Any]) -> dict[str, Any]:
    old_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(ROW_TIMEOUT_SECONDS)
    try:
        response = build_live_chat_response(ChatRequest(message=str(probe["query"])))
    except RowTimeout:
        return {
            "id": probe["id"],
            "kind": probe["kind"],
            "query": probe["query"],
            "selected_skill": None,
            "answer_mode": None,
            "authority_owner": None,
            "resource_plan_purposes": [],
            "phase_contract": [],
            "dispatch_schedule": [],
            "degrade_reason": None,
            "execution_result": None,
            "execution_block_reason": None,
            "primary_shape": None,
            "human_review_type": None,
            "has_mitre_panel": False,
            "has_reference_panel": False,
            "error": f"row_timeout:{ROW_TIMEOUT_SECONDS}s",
        }
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    payload = response.model_dump(mode="json")
    trace = payload.get("control_plane_trace") if isinstance(payload.get("control_plane_trace"), dict) else {}
    evidence_plan = trace.get("evidence_plan") if isinstance(trace.get("evidence_plan"), dict) else {}
    resource_plan = evidence_plan.get("resource_plan") if isinstance(evidence_plan.get("resource_plan"), dict) else {}
    plan_dispatch = trace.get("plan_dispatch") if isinstance(trace.get("plan_dispatch"), dict) else {}
    debug = build_debug_summary(payload=payload, control_plane_trace=trace)
    schedule = debug.get("schedule") if isinstance(debug.get("schedule"), dict) else {}
    resource_steps = resource_plan.get("steps") if isinstance(resource_plan.get("steps"), list) else []
    resource_purposes = [
        str(step.get("purpose"))
        for step in resource_steps
        if isinstance(step, dict) and step.get("purpose")
    ]
    phase_contract = [str(item) for item in (schedule.get("phase_names") or [])]
    dispatch_schedule = [str(item) for item in (schedule.get("dispatch_schedule") or [])]
    dispatch_source = str(plan_dispatch.get("dispatch_source") or "")
    if phase_contract:
        authority_owner = "resource_plan_phase_contract"
    elif resource_plan and payload.get("answer_mode") == "rag_only":
        authority_owner = "resource_planner_rag_lane"
    elif resource_plan:
        authority_owner = "resource_plan"
    elif dispatch_source == "canonical_non_planned":
        authority_owner = "canonical_non_planned"
    else:
        authority_owner = "deterministic_non_planned"
    answer_shape = trace.get("answer_shape") if isinstance(trace.get("answer_shape"), dict) else {}
    analyst_response = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else {}
    structured_context = payload.get("structured_context") if isinstance(payload.get("structured_context"), dict) else {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    deterministic_shape = classify_answer_shape(str(probe["query"])).primary_shape
    return {
        "id": probe["id"],
        "kind": probe["kind"],
        "query": probe["query"],
        "selected_skill": payload.get("selected_skill"),
        "answer_mode": payload.get("answer_mode"),
        "authority_owner": authority_owner,
        "resource_plan_purposes": resource_purposes,
        "phase_contract": phase_contract,
        "dispatch_schedule": dispatch_schedule,
        "degrade_reason": schedule.get("degrade_reason"),
        "execution_result": execution.get("execution_status_label") or execution.get("status"),
        "execution_block_reason": execution.get("block_reason"),
        "primary_shape": answer_shape.get("primary_shape") or _dig(payload, "routing_skill_resolution", "answer_shape", "primary_shape") or deterministic_shape,
        "human_review_type": _dig(payload, "human_review", "review_type"),
        "has_mitre_panel": bool(payload.get("mitre_mappings") or analyst_response.get("mitre")),
        "has_reference_panel": bool(
            analyst_response.get("reference_facts") or structured_context.get("reference_facts")
        ),
    }


def _render(rows: list[dict[str, Any]]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Reference Knowledge Probe Baseline",
        "",
        f"Generated: {now}",
        "",
        "Current baseline for the reference-knowledge probe contract. P1-P4 should route through `reference_taxonomy` / `reference_knowledge`; P5/P6/N1-N4 are frozen non-regression rows.",
        "",
        "| ID | Kind | Route | Answer | Authority owner | Resource purposes | PhaseContract | Dispatch | HIL | Result |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        purposes = ",".join(str(item) for item in row.get("resource_plan_purposes") or [])
        phases = ",".join(str(item) for item in row.get("phase_contract") or [])
        dispatch = ",".join(str(item) for item in row.get("dispatch_schedule") or [])
        lines.append(
            "| {id} | {kind} | {selected_skill} | {answer_mode} | {authority_owner} | {purposes} | {phases} | {dispatch} | {human_review_type} | {execution_result} |".format(
                purposes=purposes,
                phases=phases,
                dispatch=dispatch,
                **{key: row.get(key) or "" for key in ("id", "kind", "selected_skill", "answer_mode", "authority_owner", "human_review_type", "execution_result")},
            )
        )
    lines.extend(
        [
            "",
            "## Frozen Non-Regression Contract",
            "",
            "- Authority fields come from ResourcePlan, PhaseContract/merge, and the current dispatch/execution result; retired `pipeline_dispatch.decision` fields are not read or reconstructed.",
            "- P5/P6/N1-N4 current routes are the non-regression baseline for item 18.",
            "- N3 intentionally duplicates the alert-mapping guard class covered by P5.",
            "- This file is updated deliberately when P1/P2 flip red to green; the probe script should not be used for silent baseline drift.",
            "",
            "```json",
            json.dumps(rows, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


#: Fields that define the contract. ``query`` is echoed for readability and
#: ``kind`` is fixture metadata; neither is a routing decision, so drift in them
#: means the probe set changed rather than the pipeline regressing.
COMPARED_FIELDS: tuple[str, ...] = (
    "selected_skill",
    "answer_mode",
    "authority_owner",
    "resource_plan_purposes",
    "phase_contract",
    "dispatch_schedule",
    "degrade_reason",
    "execution_result",
    "execution_block_reason",
    "primary_shape",
    "human_review_type",
    "has_mitre_panel",
    "has_reference_panel",
)


def _parse_baseline_rows(text: str) -> list[dict[str, Any]] | None:
    """Read the structured rows embedded in the baseline's fenced json block.

    The markdown table is for humans; the json block is authoritative because it
    carries list/bool types the table flattens to strings.
    """
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if not match:
        return None
    try:
        rows = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return rows if isinstance(rows, list) else None


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in COMPARED_FIELDS:
        value = row.get(field)
        out[field] = list(value) if isinstance(value, list) else value
    return out


def _compare(current: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    by_id = {str(row.get("id")): row for row in baseline}
    lines: list[str] = []
    ok = True

    for row in current:
        probe_id = str(row.get("id"))
        old = by_id.pop(probe_id, None)
        if old is None:
            ok = False
            lines.append(f"  {probe_id:<4} DRIFT  not present in baseline")
            continue
        if row.get("error"):
            ok = False
            lines.append(f"  {probe_id:<4} DRIFT  probe errored: {row['error']}")
            continue
        new_n, old_n = _normalize(row), _normalize(old)
        if new_n == old_n:
            lines.append(f"  {probe_id:<4} PASS   {row.get('selected_skill')} / {row.get('answer_mode')}")
            continue
        ok = False
        deltas = [
            f"{field}: {old_n[field]!r} -> {new_n[field]!r}"
            for field in COMPARED_FIELDS
            if old_n[field] != new_n[field]
        ]
        lines.append(f"  {probe_id:<4} DRIFT  " + "; ".join(deltas))

    for missing in by_id:
        ok = False
        lines.append(f"  {missing:<4} DRIFT  in baseline but not produced by this run")

    return ok, lines


def _run_probes() -> list[dict[str, Any]]:
    probes = json.loads(PROBES.read_text(encoding="utf-8"))
    return [_route_row(probe) for probe in probes]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="compare against the frozen baseline and write nothing (default)",
    )
    mode.add_argument(
        "--update-baseline",
        action="store_true",
        help="deliberately rewrite the frozen baseline; never used by a verification gate",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the rendered report to this scratch path instead of the baseline",
    )
    args = ap.parse_args()

    rows = _run_probes()
    rendered = _render(rows)

    if args.update_baseline:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(rendered, encoding="utf-8")
        print(json.dumps({"probe_count": len(rows), "baseline": str(OUT), "mode": "update-baseline"}, sort_keys=True))
        return 0

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(json.dumps({"probe_count": len(rows), "report": str(args.out), "mode": "report"}, sort_keys=True))

    # --check is the default: comparison happens unless the caller only wanted a
    # scratch report written.
    if args.out is not None and not args.check:
        return 0

    try:
        baseline_text = OUT.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read baseline {OUT}: {exc}", file=sys.stderr)
        return 2

    baseline_rows = _parse_baseline_rows(baseline_text)
    if baseline_rows is None:
        print(f"baseline {OUT} has no parseable json row block", file=sys.stderr)
        return 2

    ok, lines = _compare(rows, baseline_rows)
    print(f"reference probe contract vs {OUT.name} ({len(rows)} probes):")
    for line in lines:
        print(line)
    if not ok:
        print(
            "\nDRIFT: routing changed against the frozen contract. If this is intended, "
            "say so explicitly and re-run with --update-baseline.",
            file=sys.stderr,
        )
        return 1
    print("all probes match the frozen baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
