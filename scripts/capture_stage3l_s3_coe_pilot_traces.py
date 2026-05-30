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


def main() -> int:
    import pytest

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
    print(json.dumps({"written": str(out_path), "scenario_count": len(scenarios)}, indent=2))
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
