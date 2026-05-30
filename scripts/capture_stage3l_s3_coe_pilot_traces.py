#!/usr/bin/env python3
"""Capture route_authority_compare traces for COE cov.q046 pilot verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "backend"
sys.path.insert(0, str(_BACKEND))

from app.api.routes_chat import chat  # noqa: E402
from app.observation.cov_q046_observation import (  # noqa: E402
    render_observation_markdown_table,
    run_observation_window,
)
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID  # noqa: E402
from app.schemas.requests import ChatRequest  # noqa: E402
from app.tests.test_route_plan_stage3k_r2 import (  # noqa: E402
    _patch_common_chat_dependencies,
    _valid_route_plan_candidate,
)
import app.config as config_module  # noqa: E402

QUERY = "Find top 10 users with failed Okta logins in the last 24 hours."


def _cov_q046_candidate_with_slots() -> dict[str, Any]:
    candidate = _valid_route_plan_candidate()
    candidate["parameters"]["threshold_ref"] = {"policy_id": "failed_login_excessive_default"}
    candidate["parameters"]["time_window"] = "last_24_hours"
    return candidate


def _compare_slice(response: Any) -> dict[str, Any]:
    shadow = response.route_plan_shadow
    compare = shadow.route_authority_compare if shadow else None
    if not compare:
        return {"error": "route_plan_shadow or route_authority_compare missing"}
    keys = (
        "coverage_id_resolved",
        "operation_authoritative_applied",
        "operation_authoritative_enabled",
        "authority_applied",
        "authority_eligible",
        "authority_fallback_reason",
        "authority_decision",
        "authority_holder",
        "authority_trace",
        "planning_primary_skill",
        "selected_skill",
        "legacy_selected_skill_preserved",
        "global_enabled",
        "coverage_id_allowlisted",
        "migration_phase",
    )
    return {key: compare.get(key) for key in keys if key in compare}


def _run_scenario(
    name: str,
    *,
    authoritative: bool,
    allowlist: str,
    candidate_factory,
    monkeypatch_module: Any,
) -> dict[str, Any]:
    mp = monkeypatch_module.MonkeyPatch()
    try:
        mp.setattr(
            config_module.settings,
            "route_authority_operation_authoritative_enabled",
            authoritative,
        )
        mp.setattr(
            config_module.settings,
            "route_authority_operation_coverage_allowlist",
            allowlist,
        )
        _patch_common_chat_dependencies(mp, skill="attack_discovery")
        mp.setattr(
            "app.api.routes_chat._route_plan_shadow_candidate",
            lambda query: candidate_factory(),
        )
        response = chat(ChatRequest(message=QUERY))
        return {
            "scenario": name,
            "env": {
                "ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED": authoritative,
                "ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST": allowlist or "(empty)",
            },
            "response_selected_skill": response.selected_skill,
            "execution_executed_spl": response.execution.executed_spl if response.execution else None,
            "route_authority_compare": _compare_slice(response),
        }
    finally:
        mp.undo()


def _append_observation_run(records: list[dict[str, Any]]) -> None:
    runs_path = _REPO / "docs" / "stage3l_s3_cov_q046_observation_runs.jsonl"
    with runs_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _run_varied_observation_window(monkeypatch_module: Any, *, record_run: bool) -> int:
    mp = monkeypatch_module.MonkeyPatch()
    try:
        result = run_observation_window(mp, include_baselines=True)
    finally:
        mp.undo()
    summary_path = _REPO / "docs" / "stage3l_s3_cov_q046_observation_summary.json"
    summary_payload = {
        "window_start": result.window_start,
        "window_end": result.window_end,
        "status": result.status,
        "closure_reason": result.closure_reason,
        "authority_eligible": result.authority_eligible,
        "unexpected_disagreement_count": result.unexpected_disagreement_count,
        "expected_disagreement_count": result.expected_disagreement_count,
        "disagreement_counts": result.summary_counts(),
        "blockers": result.blockers,
        "pilot_coverage_id": COV_Q046_PILOT_COVERAGE_ID,
        "note": "Stage 3L-S3 Step 7 varied-input observation; authority_eligible does not enable production.",
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")

    log_path = _REPO / "docs" / "stage3l_s3_cov_q046_observation_log.md"
    _update_observation_log_markdown(log_path, result)

    if record_run:
        _append_observation_run([row.to_jsonl_record() for row in result.rows])

    print(json.dumps(summary_payload, indent=2))
    exit_code = 0
    if result.status != "closed":
        print("OBSERVATION WINDOW OPEN — blockers:", result.blockers, file=sys.stderr)
        exit_code = 1
    return exit_code


def _update_observation_log_markdown(log_path: Path, result: Any) -> None:
    text = log_path.read_text(encoding="utf-8")
    table = render_observation_markdown_table(result)

    window_block = (
        f"**Status:** Observation **{result.status}** — "
        f"{result.closure_reason}; "
        f"`cov.q046` authority-eligible={str(result.authority_eligible).lower()} "
        f"(production cutover remains separate COE decision).\n\n"
        f"| Observation window | Status |\n"
        f"|--------------------|--------|\n"
        f"| Start | {result.window_start} |\n"
        f"| End | {result.window_end} |\n"
        f"| Unexpected disagreements | {result.unexpected_disagreement_count} "
        f"(expected: {result.expected_disagreement_count}) |\n"
        f"| Closure | {result.closure_reason} |\n"
    )

    if "**Status:** Observation **active**" in text:
        text = text.replace(
            text.split("---\n\n## Config")[0],
            f"# Stage 3L-S3 cov.q046 Observation Log\n\n"
            f"**Pilot:** `cov.q046.excessive_failed_logins_sample`  \n"
            f"**COE sign-off:** [stage3l_s3_step3_coe_gate_review.md](stage3l_s3_step3_coe_gate_review.md) (2026-05-29)  \n"
            f"**Capture script:** `python3 scripts/capture_stage3l_s3_coe_pilot_traces.py --varied-window`  \n"
            f"**Record observation run:** add `--record-run` → appends to "
            f"[stage3l_s3_cov_q046_observation_runs.jsonl](stage3l_s3_cov_q046_observation_runs.jsonl)  \n"
            f"**Summary JSON:** [stage3l_s3_cov_q046_observation_summary.json](stage3l_s3_cov_q046_observation_summary.json)  \n"
            f"**Fixture:** `backend/app/tests/fixtures/stage3l_s3_cov_q046_observation_inputs.json`  \n\n"
            f"{window_block}\n---\n\n",
        )

    marker = "## Observation window entries"
    if marker in text:
        before, _after = text.split(marker, 1)
        rest = _after.split("\n", 1)[-1]
        # drop old table rows until next ##
        if "## How to record" in rest:
            _, tail = rest.split("## How to record", 1)
            rest = "## How to record" + tail
        else:
            rest = ""
        text = before + marker + "\n\n" + table + "\n" + rest

    log_path.write_text(text, encoding="utf-8")


def main() -> int:
    import argparse
    import pytest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--record-run",
        action="store_true",
        help="Append scenario summary to docs/stage3l_s3_cov_q046_observation_runs.jsonl",
    )
    parser.add_argument(
        "--varied-window",
        action="store_true",
        help="Run Stage 3L-S3 Step 7 varied-input observation window closure harness",
    )
    args = parser.parse_args()

    if args.varied_window:
        return _run_varied_observation_window(pytest, record_run=args.record_run)

    scenarios = [
        _run_scenario(
            "default_production_safe_fallback",
            authoritative=False,
            allowlist="",
            candidate_factory=_cov_q046_candidate_with_slots,
            monkeypatch_module=pytest,
        ),
        _run_scenario(
            "lab_pilot_happy_path",
            authoritative=True,
            allowlist=COV_Q046_PILOT_COVERAGE_ID,
            candidate_factory=_cov_q046_candidate_with_slots,
            monkeypatch_module=pytest,
        ),
        _run_scenario(
            "lab_pilot_missing_threshold_fallback",
            authoritative=True,
            allowlist=COV_Q046_PILOT_COVERAGE_ID,
            candidate_factory=_valid_route_plan_candidate,
            monkeypatch_module=pytest,
        ),
    ]

    out_path = _REPO / "docs" / "stage3l_s3_step3_coe_pilot_verification_traces.json"
    payload = {
        "pilot_coverage_id": COV_Q046_PILOT_COVERAGE_ID,
        "query": QUERY,
        "note": "cov.q046 only; mock route_plan_shadow candidate via test hook",
        "scenarios": scenarios,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.record_run:
        _append_observation_run(
            [
                {
                    "recorded_at": scenarios[0]["route_authority_compare"].get("recorded_at"),
                    "scenario": item["scenario"],
                    "operation_authoritative_applied": item["route_authority_compare"].get(
                        "operation_authoritative_applied"
                    ),
                    "authority_fallback_reason": item["route_authority_compare"].get(
                        "authority_fallback_reason"
                    ),
                    "authority_holder": item["route_authority_compare"].get("authority_holder"),
                    "selected_skill": item["route_authority_compare"].get("selected_skill"),
                    "legacy_selected_skill_preserved": item["route_authority_compare"].get(
                        "legacy_selected_skill_preserved"
                    ),
                }
                for item in scenarios
            ]
        )
    print(json.dumps({"written": str(out_path), "scenario_count": len(scenarios)}, indent=2))
    if args.record_run:
        print("appended observation run to docs/stage3l_s3_cov_q046_observation_runs.jsonl")
    for item in scenarios:
        compare = item.get("route_authority_compare") or {}
        print(
            f"\n=== {item['scenario']} ===\n"
            f"  applied={compare.get('operation_authoritative_applied')} "
            f"fallback={compare.get('authority_fallback_reason')}\n"
            f"  holder={compare.get('authority_holder')}\n"
            f"  trace={compare.get('authority_trace')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
