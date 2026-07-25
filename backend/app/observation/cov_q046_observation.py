"""Stage 3L-S3 Step 7: cov.q046 varied-input observation window runner.

Observation/shadow only. Does not enable production authority or mutate /chat defaults.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.api.routes_chat import chat
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID
from app.routing.route_authority_gate import (
    FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED,
    FALLBACK_GLOBAL_KILL_SWITCH_DISABLED,
    FALLBACK_MISSING_THRESHOLD_REF,
    FALLBACK_MISSING_TIME_WINDOW,
)
from app.schemas.requests import ChatRequest
from app.tests.test_route_plan_stage3k_r2 import (
    FakeTelemetry,
    _patch_common_chat_dependencies,
    _valid_route_plan_candidate,
)

InputType = Literal["in_pattern", "near_miss", "missing_slot"]
DisagreementClass = Literal["none", "expected", "unexpected"]
RunMode = Literal["prod_defaults", "lab_pilot"]

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "stage3l_s3_cov_q046_observation_inputs.json"
)

FALLBACK_NO_VALIDATED_ROUTE_PLAN_SHADOW = "no_validated_route_plan_shadow"

MISSING_SLOT_FALLBACKS = frozenset(
    {
        FALLBACK_MISSING_THRESHOLD_REF,
        FALLBACK_MISSING_TIME_WINDOW,
        FALLBACK_NO_VALIDATED_ROUTE_PLAN_SHADOW,
        FALLBACK_GLOBAL_KILL_SWITCH_DISABLED,
    }
)


@dataclass
class ObservationRow:
    timestamp: str
    case_id: str
    run_mode: RunMode
    input_phrasing: str
    input_type: InputType
    expected_route: dict[str, Any]
    actual_route: dict[str, Any]
    coverage_id: str | None
    selected_skill: str | None
    planning_primary_skill: str | None
    bridge_status: str | None
    route_authority_compare: dict[str, Any]
    operation_authoritative_applied: bool | None
    authority_fallback_reason: str | None
    disagreement_flag: bool
    disagreement_class: DisagreementClass
    unexpected_reasons: list[str] = field(default_factory=list)
    notes: str = ""

    def to_jsonl_record(self) -> dict[str, Any]:
        return asdict(self)


def load_observation_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or FIXTURE_PATH
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def lab_shadow_templates() -> dict[str, dict[str, Any]]:
    """Validated route-plan candidates for lab authority harness (not production routing)."""
    base = _valid_route_plan_candidate()
    slotted = deepcopy(base)
    slotted["parameters"]["threshold_ref"] = {"policy_id": "failed_login_excessive_default"}
    slotted["parameters"]["time_window"] = "last_24_hours"
    slotted["time_window"] = "last_24_hours"

    no_threshold = deepcopy(base)
    no_threshold["parameters"].pop("threshold_ref", None)

    no_time = deepcopy(base)
    no_time["parameters"].pop("time_window", None)
    no_time["time_window"] = ""

    threshold_spike = deepcopy(base)
    threshold_spike["primary_skill"] = "threshold_anomaly"
    threshold_spike["pattern_id"] = "auth_failed_login_spike"
    threshold_spike["operation_type"] = "threshold"
    threshold_spike["parameters"]["threshold_ref"] = {"policy_id": "failed_login_spike_default"}
    threshold_spike["parameters"]["time_window"] = "last_24_hours"

    sequence_after_fail = deepcopy(base)
    sequence_after_fail["primary_skill"] = "sequence_detection"
    sequence_after_fail["pattern_id"] = "success_after_failed_logins"
    sequence_after_fail["operation_type"] = "sequence"
    sequence_after_fail["parameters"]["threshold_ref"] = {"policy_id": "x"}
    sequence_after_fail["parameters"]["time_window"] = "last_24_hours"

    entity_lookup = deepcopy(base)
    entity_lookup["primary_skill"] = "entity_context_lookup"
    entity_lookup["pattern_id"] = "privileged_failed_logins"
    entity_lookup["operation_type"] = "lookup"
    entity_lookup["parameters"]["threshold_ref"] = {"policy_id": "x"}
    entity_lookup["parameters"]["time_window"] = "last_24_hours"

    return {
        "cov_q046_slotted": slotted,
        "cov_q046_no_threshold": no_threshold,
        "cov_q046_no_time_window": no_time,
        "cov_q062_threshold_spike": threshold_spike,
        "sequence_success_after_failures": sequence_after_fail,
        "entity_context_lookup_primary": entity_lookup,
    }


def _compare_from_response(response: Any) -> dict[str, Any]:
    shadow = response.route_plan_shadow
    if shadow is None or shadow.route_authority_compare is None:
        return {}
    return dict(shadow.route_authority_compare)


def _actual_route_slice(compare: dict[str, Any], shadow: Any) -> dict[str, Any]:
    return {
        "coverage_id": compare.get("coverage_id_resolved"),
        "pattern_id": getattr(shadow, "pattern_id", None) if shadow else None,
        "primary_skill": compare.get("planning_primary_skill")
        or compare.get("candidate_primary_skill")
        or (getattr(shadow, "primary_skill", None) if shadow else None),
        "route_status": getattr(shadow, "route_status", None) if shadow else None,
    }


def _skill_drift_disagreement(selected_skill: str | None, planning: str | None) -> bool:
    if not selected_skill or not planning:
        return False
    return selected_skill.strip() != planning.strip()


def classify_observation_row(
    case: dict[str, Any],
    *,
    run_mode: RunMode,
    compare: dict[str, Any],
    actual_route: dict[str, Any],
    selected_skill: str | None,
) -> tuple[DisagreementClass, list[str], bool, str]:
    """Return disagreement_class, unexpected_reasons, disagreement_flag, notes."""
    unexpected: list[str] = []
    input_type: InputType = case["input_type"]
    expected = case.get("expected_route") or {}

    applied = compare.get("operation_authoritative_applied")
    fallback = compare.get("authority_fallback_reason")
    coverage = compare.get("coverage_id_resolved")
    planning = compare.get("planning_primary_skill") or actual_route.get("primary_skill")

    if run_mode == "prod_defaults":
        if applied is not False:
            unexpected.append("prod_operation_authoritative_applied_not_false")
        if fallback != FALLBACK_GLOBAL_KILL_SWITCH_DISABLED:
            unexpected.append(f"prod_fallback_not_kill_switch:{fallback}")
        if input_type == "near_miss" and coverage == COV_Q046_PILOT_COVERAGE_ID:
            unexpected.append("prod_near_miss_resolved_cov_q046")
        if input_type == "missing_slot" and applied is True:
            unexpected.append("prod_missing_slot_authority_applied")

    if run_mode == "lab_pilot":
        lab_expect_applied = case.get("lab_expect_authority_applied")
        if lab_expect_applied is True:
            if applied is not True:
                unexpected.append("lab_in_pattern_authority_not_applied")
            if coverage != COV_Q046_PILOT_COVERAGE_ID:
                unexpected.append(f"lab_in_pattern_wrong_coverage:{coverage}")
            exp_primary = expected.get("primary_skill")
            if exp_primary and planning != exp_primary:
                unexpected.append(f"lab_planning_skill_mismatch:{planning}")
        elif lab_expect_applied is False:
            if applied is True:
                unexpected.append("lab_authority_applied_when_forbidden")
            if input_type == "near_miss" and coverage == COV_Q046_PILOT_COVERAGE_ID:
                unexpected.append("lab_near_miss_claimed_cov_q046")
            expected_fallback = case.get("lab_expect_fallback")
            alternatives = case.get("lab_expect_fallback_alternatives") or []
            allowed_fallbacks = {expected_fallback, *alternatives} if expected_fallback else set()
            if allowed_fallbacks and fallback not in allowed_fallbacks:
                unexpected.append(f"lab_fallback_mismatch:{fallback}")
            if input_type == "missing_slot":
                allowed = {
                    FALLBACK_MISSING_THRESHOLD_REF,
                    FALLBACK_MISSING_TIME_WINDOW,
                    FALLBACK_NO_VALIDATED_ROUTE_PLAN_SHADOW,
                    FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED,
                    "blocked_primary_fixture_absent",
                    "bridge_incompatible",
                    "validator_blocked",
                }
                if fallback not in allowed:
                    unexpected.append(f"missing_slot_unexpected_fallback:{fallback}")

    flag = _skill_drift_disagreement(selected_skill, planning) or bool(unexpected)
    if unexpected:
        return "unexpected", unexpected, flag, "; ".join(unexpected)
    if _skill_drift_disagreement(selected_skill, planning) and applied is True:
        return (
            "expected",
            [],
            True,
            "legacy selected_skill vs route_plan primary_skill (intentional pilot drift)",
        )
    return "none", [], flag, ""


def run_chat_observation(
    case: dict[str, Any],
    *,
    run_mode: RunMode,
    monkeypatch: Any,
    authoritative: bool,
    allowlist: str,
) -> ObservationRow:
    import app.config as config_module

    mp = monkeypatch
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
    legacy = str(case.get("legacy_skill") or "attack_discovery")
    _patch_common_chat_dependencies(mp, skill=legacy)

    templates = lab_shadow_templates()
    template_key = case.get("lab_shadow_template")
    if template_key:
        mp.setattr(
            "app.chat.pipeline.build_deterministic_route_plan_candidate",
            lambda **kwargs: None,
        )

    def candidate_factory(query: str) -> dict[str, Any] | None:
        if run_mode == "prod_defaults" or not template_key:
            return None
        return deepcopy(templates[template_key])

    mp.setattr("app.api.routes_chat._route_plan_shadow_candidate", candidate_factory)
    mp.setattr("app.api.routes_chat.get_telemetry_connector", lambda: FakeTelemetry())
    mp.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())

    message = str(case["message"])
    if run_mode == "lab_pilot" and case.get("lab_message"):
        message = str(case["lab_message"])
    response = chat(ChatRequest(message=message))
    compare = _compare_from_response(response)
    shadow = response.route_plan_shadow
    actual_route = _actual_route_slice(compare, shadow)
    disagreement_class, unexpected, flag, notes = classify_observation_row(
        case,
        run_mode=run_mode,
        compare=compare,
        actual_route=actual_route,
        selected_skill=response.selected_skill,
    )

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ObservationRow(
        timestamp=stamp,
        case_id=str(case["case_id"]),
        run_mode=run_mode,
        input_phrasing=str(case["message"]),
        input_type=case["input_type"],
        expected_route=case.get("expected_route") or {},
        actual_route=actual_route,
        coverage_id=compare.get("coverage_id_resolved"),
        selected_skill=response.selected_skill,
        planning_primary_skill=compare.get("planning_primary_skill"),
        bridge_status=(
            (shadow.intent_operation_bridge or {}).get("bridge_status")
            if shadow and shadow.intent_operation_bridge
            else None
        ),
        route_authority_compare=compare,
        operation_authoritative_applied=compare.get("operation_authoritative_applied"),
        authority_fallback_reason=compare.get("authority_fallback_reason"),
        disagreement_flag=flag,
        disagreement_class=disagreement_class,
        unexpected_reasons=unexpected,
        notes=notes,
    )


def run_baseline_scenarios(monkeypatch: Any) -> list[dict[str, Any]]:
    """Preserve original three scripted baseline scenarios."""
    from app.tests.test_route_plan_stage3k_r2 import _valid_route_plan_candidate

    def _cov_q046_slotted() -> dict[str, Any]:
        candidate = _valid_route_plan_candidate()
        candidate["parameters"]["threshold_ref"] = {"policy_id": "failed_login_excessive_default"}
        candidate["parameters"]["time_window"] = "last_24_hours"
        return candidate

    query = "Find top 10 users with failed Okta logins in the last 24 hours."
    cases = [
        ("default_production_safe_fallback", False, "", _cov_q046_slotted),
        ("lab_pilot_happy_path", True, COV_Q046_PILOT_COVERAGE_ID, _cov_q046_slotted),
        ("lab_pilot_missing_threshold_fallback", True, COV_Q046_PILOT_COVERAGE_ID, _valid_route_plan_candidate),
    ]
    results: list[dict[str, Any]] = []
    import app.config as config_module

    for name, auth, allowlist, factory in cases:
        mp = monkeypatch
        mp.setattr(
            config_module.settings,
            "route_authority_operation_authoritative_enabled",
            auth,
        )
        mp.setattr(
            config_module.settings,
            "route_authority_operation_coverage_allowlist",
            allowlist,
        )
        _patch_common_chat_dependencies(mp, skill="attack_discovery")
        mp.setattr(
            "app.chat.pipeline.build_deterministic_route_plan_candidate",
            lambda **kwargs: None,
        )
        mp.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda q, f=factory: f())
        response = chat(ChatRequest(message=query))
        compare = _compare_from_response(response)
        results.append(
            {
                "scenario": name,
                "env": {
                    "ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED": auth,
                    "ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST": allowlist or "(empty)",
                },
                "response_selected_skill": response.selected_skill,
                "execution_executed_spl": response.execution.executed_spl if response.execution else None,
                "route_authority_compare": {k: compare.get(k) for k in compare},
            }
        )
    return results


@dataclass
class ObservationWindowResult:
    window_start: str
    window_end: str
    status: Literal["closed", "open"]
    closure_reason: str
    authority_eligible: bool
    unexpected_disagreement_count: int
    expected_disagreement_count: int
    rows: list[ObservationRow] = field(default_factory=list)
    baseline_scenarios: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def summary_counts(self) -> dict[str, int]:
        counts = {"none": 0, "expected": 0, "unexpected": 0}
        for row in self.rows:
            counts[row.disagreement_class] = counts.get(row.disagreement_class, 0) + 1
        return counts


def run_observation_window(
    monkeypatch: Any,
    *,
    fixture_path: Path | None = None,
    include_baselines: bool = True,
) -> ObservationWindowResult:
    fixture = load_observation_fixture(fixture_path)
    window = fixture.get("observation_window") or {}
    cases = fixture.get("cases") or []
    rows: list[ObservationRow] = []

    for case in cases:
        rows.append(
            run_chat_observation(
                case,
                run_mode="prod_defaults",
                monkeypatch=monkeypatch,
                authoritative=False,
                allowlist="",
            )
        )
        rows.append(
            run_chat_observation(
                case,
                run_mode="lab_pilot",
                monkeypatch=monkeypatch,
                authoritative=True,
                allowlist=COV_Q046_PILOT_COVERAGE_ID,
            )
        )

    unexpected_count = sum(1 for row in rows if row.disagreement_class == "unexpected")
    expected_count = sum(1 for row in rows if row.disagreement_class == "expected")
    blockers = sorted(
        {reason for row in rows for reason in row.unexpected_reasons},
    )

    window_start = str(window.get("start") or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    window_end = str(window.get("end") or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

    if unexpected_count == 0 and len(cases) >= 20:
        status: Literal["closed", "open"] = "closed"
        closure_reason = "zero_unexpected_disagreements"
        authority_eligible = True
    else:
        status = "open"
        closure_reason = "blocked"
        authority_eligible = False
        if unexpected_count:
            blockers.append(f"unexpected_disagreement_count={unexpected_count}")
        if len(cases) < 20:
            blockers.append(f"insufficient_cases={len(cases)}")

    baselines: list[dict[str, Any]] = []
    if include_baselines:
        baselines = run_baseline_scenarios(monkeypatch)

    return ObservationWindowResult(
        window_start=window_start,
        window_end=window_end,
        status=status,
        closure_reason=closure_reason,
        authority_eligible=authority_eligible,
        unexpected_disagreement_count=unexpected_count,
        expected_disagreement_count=expected_count,
        rows=rows,
        baseline_scenarios=baselines,
        blockers=blockers,
    )


def render_observation_markdown_table(result: ObservationWindowResult) -> str:
    lines = [
        "| Date | Case | Mode | Type | coverage_id | applied | fallback | Unexpected? | Class | Notes |",
        "|------|------|------|------|-------------|---------|----------|-------------|-------|-------|",
    ]
    for row in result.rows:
        lines.append(
            f"| {row.timestamp[:10]} | {row.case_id} | {row.run_mode} | {row.input_type} | "
            f"{row.coverage_id or '—'} | {row.operation_authoritative_applied} | "
            f"{row.authority_fallback_reason or '—'} | "
            f"{'yes' if row.disagreement_class == 'unexpected' else 'no'} | "
            f"{row.disagreement_class} | {row.notes[:80] if row.notes else '—'} |"
        )
    return "\n".join(lines) + "\n"
