"""OPTIONAL_PHASE_S S3 — Layer 1a compiler early projection + Q11 preserved."""

from __future__ import annotations

import json
from pathlib import Path

from app.spl.draft_quality import evaluate_draft_quality
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl, compile_plan_to_spl
from app.spl.rewrite_guard import assert_rewrite_preserves
from app.spl.spl_intent_spec import build_spl_intent_spec

REPO = Path(__file__).resolve().parents[3]
FREEZE = REPO / "docs/evals/spl_optimization/authority_baseline_v1.json"
BEFORE_AFTER = REPO / "docs/evals/spl_optimization/s3_compiler_before_after_v1.json"

_LEGACY_PLAN = {
    "detection_family": "ot_modbus_unauthorized_write",
    "data_domain": "ot_network",
    "time_window_hours": 24,
    "filters": [{"field": "protocol", "match": "modbus"}],
    "group_by": ["src_ip", "dest_ip"],
    "metric": "count",
}


def test_q11_sort_preserved_on_rolling() -> None:
    spl = compile_intent_spec_to_spl(
        build_spl_intent_spec(
            "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
        )
    )
    assert "| sort 0 + _time |" in f" {spl} ".replace("  ", " ") or "sort 0 + _time" in spl
    report = evaluate_draft_quality(spl)
    assert not any(
        item.rule_id == "SOC-STD-SPL-001-Q11" and item.severity == "hard_fail"
        for item in report.findings
    )


def test_early_fields_projection_on_legacy_plan() -> None:
    spl = compile_plan_to_spl(_LEGACY_PLAN)
    assert "| fields " in spl
    assert "protocol=\"modbus\"" in spl or 'protocol="modbus"' in spl
    # Filter still in base search before first pipe.
    base = spl.split("|", 1)[0]
    assert "protocol=" in base


def test_rewrite_preserves_vs_s0_freeze_candidates() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    deltas: list[dict] = []
    for row in freeze["rows"]:
        if row.get("producer_path") != "plan_compiler" or not row.get("candidate_spl"):
            continue
        old = row["candidate_spl"]
        if row["row_id"] == "compiler.plan.ot_modbus_unauthorized_write":
            new = compile_plan_to_spl(_LEGACY_PLAN)
        elif row["row_id"].startswith("compiler.intent."):
            queries = {
                "compiler.intent.rolling": (
                    "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
                ),
                "compiler.intent.trend": "hourly failed-login trend over the last 24 hours",
                "compiler.intent.sequence": (
                    "password change followed by successful login within 5 minutes"
                ),
            }
            new = compile_intent_spec_to_spl(build_spl_intent_spec(queries[row["row_id"]]))
        else:
            continue
        result = assert_rewrite_preserves(old, new)
        assert result["verdict"] == "PASS", (row["row_id"], result["violations"])
        if old != new:
            deltas.append({"row_id": row["row_id"], "before": old, "after": new})
    BEFORE_AFTER.parent.mkdir(parents=True, exist_ok=True)
    BEFORE_AFTER.write_text(
        json.dumps({"shapes_changed": deltas, "count": len(deltas)}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    # Layer 1a must change at least one plan-compiler shape vs the S0 freeze snapshot.
    assert len(deltas) >= 1, deltas


def test_s3_authority_one_way_vs_freeze() -> None:
    from app.safeguards.spl_validator import validate_spl

    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    for row in freeze["rows"]:
        if row.get("producer_path") != "plan_compiler" or not row.get("candidate_spl"):
            continue
        if row["row_id"] == "compiler.plan.ot_modbus_unauthorized_write":
            new = compile_plan_to_spl(_LEGACY_PLAN)
        else:
            queries = {
                "compiler.intent.rolling": (
                    "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
                ),
                "compiler.intent.trend": "hourly failed-login trend over the last 24 hours",
                "compiler.intent.sequence": (
                    "password change followed by successful login within 5 minutes"
                ),
            }
            new = compile_intent_spec_to_spl(build_spl_intent_spec(queries[row["row_id"]]))
        v = validate_spl(new)
        d = v if isinstance(v, dict) else v.model_dump()
        assert bool(d.get("approved")) == bool(row["approved"])
        assert bool(d.get("execution_eligible") or False) == bool(row["execution_eligible"])
        # normalized_spl stays null for placeholder compiler output (non-optimized authority identity)
        assert (d.get("normalized_spl") or None) == (row["normalized_spl"] or None)
