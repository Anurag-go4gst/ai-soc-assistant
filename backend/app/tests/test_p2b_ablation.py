"""§4.6 three-profile ablation — structural gate invariants (offline)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "run_p2b_ablation.py"
_spec = importlib.util.spec_from_file_location("run_p2b_ablation", _SCRIPT)
assert _spec and _spec.loader
abl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abl)


def _row(**kw):
    base = {
        "id": "r",
        "category": "soc",
        "stratum": "spl_generation_only",
        "skill": "attack_discovery",
        "profile_1_capability": ["deterministic_card"],
        "profile_2_capability": ["asset:spl", "deterministic_card"],
        "profile_3_capability": ["asset:spl", "deterministic_card", "role:mcp_tool_plan_shadow"],
        "routed_resource_legs": ["spl"],
        "enabled_roles": ["mcp_tool_plan_shadow"],
        "role_ablation": {"mcp_tool_plan_shadow": {"consumer": "control_plane_trace.mcp_tool_plan_shadow"}},
        "delta_p2_p1": 1,
        "delta_p3_p2": 1,
    }
    base.update(kw)
    return base


def test_clean_row_passes_gate() -> None:
    assert abl._gate([_row()]) == []


def test_non_monotonic_capability_fails() -> None:
    bad = _row(profile_2_capability=["asset:spl"])  # drops deterministic_card -> P1 not subset of P2
    failures = abl._gate([bad])
    assert any("monotonic" in f for f in failures)


def test_boundary_row_with_assets_fails() -> None:
    bad = _row(
        stratum="unsafe_execution",
        routed_resource_legs=["spl"],
        enabled_roles=[],
        role_ablation={},
        profile_3_capability=["asset:spl", "deterministic_card"],
    )
    failures = abl._gate([bad])
    assert any("boundary row routed asset legs" in f for f in failures)


def test_boundary_row_with_roles_fails() -> None:
    bad = _row(
        stratum="out_of_scope",
        routed_resource_legs=[],
        profile_2_capability=["deterministic_card"],
        enabled_roles=["governed_composer"],
        role_ablation={"governed_composer": {"consumer": "analyst_response.narrative"}},
        profile_3_capability=["deterministic_card", "role:governed_composer"],
    )
    failures = abl._gate([bad])
    assert any("boundary row enabled LLM roles" in f for f in failures)


def test_enabled_role_without_consumer_fails() -> None:
    bad = _row(role_ablation={"mcp_tool_plan_shadow": {"consumer": None}})
    failures = abl._gate([bad])
    assert any("no consumer" in f for f in failures)


def test_non_boundary_row_gaining_nothing_fails() -> None:
    bad = _row(
        routed_resource_legs=[],
        enabled_roles=[],
        role_ablation={},
        profile_2_capability=["deterministic_card"],
        profile_3_capability=["deterministic_card"],
        delta_p2_p1=0,
        delta_p3_p2=0,
    )
    failures = abl._gate([bad])
    assert any("gains nothing" in f for f in failures)


def test_resource_leg_probe_boundary_empty() -> None:
    assert abl._routed_resource_legs(
        query="delete all logs now", category="soc", stratum="unsafe_execution", skill="knowledge_recall"
    ) == []


def test_resource_leg_probe_cve_detected() -> None:
    legs = abl._routed_resource_legs(
        query="Is CVE-2024-1234 exploitable on our hosts?",
        category="cve",
        stratum="knowledge_only",
        skill="knowledge_recall",
    )
    assert "cve" in legs
