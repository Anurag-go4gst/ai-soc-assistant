"""P8 L3-1 — frozen live-eval bank and thresholds. No live model."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.llm.policy.evaluation import REQUIRED_FROZEN_METRICS, contract_for_role, freeze_thresholds
from app.llm.policy.role_inventory import blocked_role_ids
from app.llm.sidecar_clients import _REASONING_ALLOWED_ROLES
from app.tests.support.l2_bank_manifest import CASES

_ROOT = Path(__file__).resolve().parents[3]
_BANK = _ROOT / "docs/evals/p8_l3/bank_v1.json"
_THRESHOLDS = _ROOT / "docs/evals/p8_l3/thresholds_v1.json"
_RUNNER = _ROOT / "scripts/eval_p8_l3_live.py"
_PRODUCT_SHA = "b6e4befe9a79dd722a09a09fdd345bae82880884"
_BLOCKED = {
    "mitre_reasoner",
    "missing_evidence_reasoner",
    "risk_rationale_reasoner",
    "plan_delta_reasoner",
    "pattern_reasoner",
    "evidence_reasoner",
    "hypothesis_reasoner",
}


def _bank() -> dict:
    return json.loads(_BANK.read_text(encoding="utf-8"))


def _thresholds() -> dict:
    return json.loads(_THRESHOLDS.read_text(encoding="utf-8"))


def test_l3_bank_is_pinned_to_the_live_eval_candidate_sha() -> None:
    bank = _bank()
    assert bank["product_sha"] == _PRODUCT_SHA
    assert bank["candidate_prompt"] is None
    assert bank["live_ab_eval_performed"] is False


def test_l3_bank_covers_required_measurement_categories() -> None:
    cats = {row["category"] for row in _bank()["rows"]}
    for required in (
        "t4_semantic",
        "spl_rolling",
        "spl_trend",
        "spl_sequence",
        "spl_ranking",
        "spl_raw_events",
        "l2_production",
        "followup_correction",
        "evidence_truth_negative",
        "investigation_planner",
        "failure_abstain",
        "prompt_role",
    ):
        assert required in cats, required


def test_l3_bank_does_not_live_invoke_blocked_reasoners() -> None:
    live_roles = {row.get("role_id") for row in _bank()["rows"] if row.get("role_id")}
    assert live_roles.isdisjoint(_BLOCKED)
    assert _BLOCKED <= set(blocked_role_ids())
    assert set(_REASONING_ALLOWED_ROLES) == {"investigation_planner"}


def test_l3_l2_anchors_refer_to_real_manifest_rows() -> None:
    known = {case.case_id for case in CASES}
    for row in _bank()["rows"]:
        anchor = row.get("l2_anchor")
        if anchor:
            assert anchor in known, f"{row['row_id']} unknown anchor {anchor}"


def test_l3_thresholds_freeze_before_any_live_score() -> None:
    floors = {k: float(v) for k, v in _thresholds()["measurement_floors"].items()}
    assert set(floors) == set(REQUIRED_FROZEN_METRICS)
    assert _thresholds()["frozen_before_live"] is True
    assert _thresholds()["product_sha"] == _PRODUCT_SHA
    for role_id in _thresholds()["roles"]:
        frozen = freeze_thresholds(role_id, floors)
        assert set(frozen.metric_names()) == set(REQUIRED_FROZEN_METRICS)


def test_l3_active_prompts_have_no_candidate() -> None:
    for role_id in ("semantic_t4", "spl_advisory_generator", "investigation_planner", "shape_advisor"):
        contract = contract_for_role(role_id)
        assert contract.candidate is None
        assert contract.eval_status == "NOT_RUN_LIVE"
        assert len(contract.active.stable_prefix_hash) == 64


def test_l3_dry_run_runner_exits_zero() -> None:
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{_ROOT / 'backend'}:{_ROOT}"
    proc = subprocess.run(
        [sys.executable, str(_RUNNER)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert len(payload["bank_hash"]) == 64
    assert payload["eval_status"] in {"DRY_RUN_READY", "BLOCKED_INFRASTRUCTURE"}
