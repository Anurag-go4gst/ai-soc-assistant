"""OPTIONAL_PHASE_S S4 — AUTO_FIX_SAFE deterministic rewrites."""

from __future__ import annotations

import json
from pathlib import Path

from app.spl.draft_quality import _Q04_OR_CHAIN_THRESHOLD
from app.spl.rewrite_guard import assert_rewrite_preserves
from app.spl.spl_auto_fix_safe import apply_auto_fix_safe, rewrite_same_field_or_to_in

REPO = Path(__file__).resolve().parents[3]
FREEZE_PATH = REPO / "docs/evals/spl_optimization/authority_baseline_v1.json"
OUT_PATH = REPO / "docs/evals/spl_optimization/s4_auto_fix_bank_v1.json"


def _long_or_chain(field: str = "EventCode", count: int | None = None) -> str:
    n = count or _Q04_OR_CHAIN_THRESHOLD
    arms = " OR ".join(f"{field}={4624 + i}" for i in range(n))
    return (
        f"search index=auth sourcetype=linux earliest=-1h latest=now {arms} "
        "| stats count | head 100"
    )


def test_or_chain_to_in_exact_values() -> None:
    v1 = _long_or_chain()
    v2, steps = rewrite_same_field_or_to_in(v1)
    assert steps == ["or_chain_to_in"]
    assert "EventCode IN (" in v2
    assert "OR EventCode=" not in v2.split("|")[0]
    guard = assert_rewrite_preserves(v1, v2)
    assert guard["verdict"] == "PASS"


def test_apply_auto_fix_applies_when_classified() -> None:
    result = apply_auto_fix_safe(_long_or_chain())
    assert result.applied
    assert not result.retained_v1
    assert result.rewrite_guard.get("verdict") == "PASS"
    assert "or_chain_to_in" in result.steps


def test_apply_auto_fix_retains_v1_on_guard_fail() -> None:
    v1 = _long_or_chain()
    # Deliberately break semantics: drop index in v2
    broken = v1.replace("index=auth", "")
    guard = assert_rewrite_preserves(v1, broken)
    assert guard["verdict"] == "FAIL"
    assert guard["retain_v1"] is True


def test_no_invented_in_value() -> None:
    v1 = _long_or_chain(count=_Q04_OR_CHAIN_THRESHOLD)
    v2, _ = rewrite_same_field_or_to_in(v1)
    # Must not contain values outside 4624..4624+n-1
    for extra in ("9999", "0000"):
        assert extra not in v2.split("IN (")[1].split(")")[0]


def test_sticky_llm_lineage_preserved_in_result() -> None:
    result = apply_auto_fix_safe(_long_or_chain(), llm_lineage=True)
    assert result.llm_lineage is True


def test_bank_rerun_authority_unchanged() -> None:
    """Re-run AUTO_FIX on freeze bank; authority fields must match S0."""
    from app.safeguards.spl_validator import validate_spl

    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    records: list[dict] = []
    false_positives = 0
    applied_count = 0
    for row in freeze["rows"]:
        spl = row.get("candidate_spl") or ""
        fix = apply_auto_fix_safe(spl)
        if fix.applied:
            applied_count += 1
        after = validate_spl(fix.candidate_spl)
        after_d = after if isinstance(after, dict) else after.model_dump()
        authority_ok = (
            bool(after_d.get("approved")) == bool(row.get("approved"))
            and after_d.get("normalized_spl") == row.get("normalized_spl")
            and bool(after_d.get("execution_eligible")) == bool(row.get("execution_eligible"))
        )
        if fix.applied and not authority_ok:
            false_positives += 1
        records.append(
            {
                "row_id": row["row_id"],
                "applied": fix.applied,
                "retained_v1": fix.retained_v1,
                "authority_ok": authority_ok,
                "steps": fix.steps,
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "applied_count": applied_count,
                "false_positives": false_positives,
                "rows": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    assert false_positives == 0
