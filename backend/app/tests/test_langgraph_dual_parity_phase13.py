"""Phase 13 LangGraph dual-run parity evaluation tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.evals.langgraph_dual_parity import (
    EXPECTED_105_COUNT,
    MANUAL_PARITY_SCENARIOS,
    SCHEMA_VERSION,
    classify_parity_row,
    load_eval_rows,
    parity_side_record,
    run_dual_parity_eval,
    validate_check_report,
)
from app.graph.planner_led_shadow_graph import governance_snapshot_from_response
from app.schemas.requests import ChatRequest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_langgraph_dual_parity_eval.py"


def test_loads_all_105_question_rows() -> None:
    rows = load_eval_rows(include_demo=False, include_manual=False)
    assert len(rows) == EXPECTED_105_COUNT
    assert rows[0]["source"] == "105_map"


def test_manual_and_demo_sets_included() -> None:
    rows = load_eval_rows()
    sources = {row["source"] for row in rows}
    assert "105_map" in sources
    assert "demo_scenario" in sources
    assert "manual" in sources
    manual_ids = {row["row_id"] for row in rows if row["source"] == "manual"}
    assert manual_ids == {item["row_id"] for item in MANUAL_PARITY_SCENARIOS}
    assert len(rows) >= EXPECTED_105_COUNT + 7


def test_report_schema_valid_on_subset() -> None:
    result = run_dual_parity_eval(limit=5, include_demo=False, include_manual=False)
    report = result.report
    assert report["schema_version"] == SCHEMA_VERSION
    assert "summary" in report
    assert "rows" in report
    assert len(report["rows"]) == 5
    row = report["rows"][0]
    assert "imperative" in row
    assert "shadow" in row
    assert row["response_category"] in {"match", "acceptable_diff", "mismatch"}


def test_unsafe_request_blocked_both_paths() -> None:
    result = run_dual_parity_eval(limit=None, include_105=False, include_demo=True, include_manual=True)
    demo_row = next(
        item
        for item in result.report["rows"]
        if item["row_id"] == "demo.unsafe_containment/execution_request"
    )
    assert demo_row["imperative"]["unsafe_blocked"] is True
    assert demo_row["shadow"]["unsafe_blocked"] is True
    assert demo_row["imperative"]["execution_executed"] is False
    assert demo_row["shadow"]["execution_executed"] is False
    manual_row = next(item for item in result.report["rows"] if item["row_id"] == "manual.unsafe_execute")
    assert manual_row["imperative"]["execution_executed"] is False
    assert manual_row["shadow"]["execution_executed"] is False


def test_sop_rag_only_no_spl_both_paths() -> None:
    result = run_dual_parity_eval(limit=None, include_105=False, include_demo=False, include_manual=True)
    row = next(item for item in result.report["rows"] if item["row_id"] == "manual.brute_force_sop")
    assert row["imperative"]["path_type"] == "rag_only"
    assert row["shadow"]["path_type"] == "rag_only"
    assert row["imperative"]["candidate_spl_present"] is False
    assert row["shadow"]["candidate_spl_present"] is False


def test_dns_and_powershell_do_not_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_dual_parity_eval(limit=None, include_105=False, include_demo=False, include_manual=True)
    for row_id in ("manual.dns_beaconing", "manual.powershell_checklist"):
        row = next(item for item in result.report["rows"] if item["row_id"] == row_id)
        assert row["imperative"]["execution_executed"] is False
        assert row["shadow"]["execution_executed"] is False


def test_phishing_enrichment_not_runtime_active_in_graph() -> None:
    result = run_dual_parity_eval(limit=None, include_105=False, include_demo=False, include_manual=True)
    row = next(item for item in result.report["rows"] if item["row_id"] == "manual.phishing_enrichment")
    assert row["shadow"]["runtime_support_status"] != "runtime_active"


def test_check_fails_on_simulated_mitre_upgrade() -> None:
    imperative = {
        "mitre_evidence_supported_techniques": [],
        "execution_executed": False,
        "unsafe_blocked": False,
        "hil_required": False,
        "path_type": "rag_only",
        "spl_generation_status": "none",
        "candidate_spl_present": False,
        "runtime_support_status": "planned",
    }
    shadow = {
        **imperative,
        "mitre_evidence_supported_techniques": ["T1110"],
    }
    category, _, critical = classify_parity_row(imperative, shadow)
    assert category == "mismatch"
    assert "mitre_evidence_upgrade" in critical
    failures = validate_check_report(
        {
            "summary": {"expected_minimum_total": 1, "total": 1},
            "rows": [{"row_id": "sim", "critical_mismatch_categories": critical}],
        }
    )
    assert failures


def test_check_fails_on_simulated_spl_mismatch() -> None:
    imperative = {
        "mitre_evidence_supported_techniques": [],
        "execution_executed": False,
        "unsafe_blocked": False,
        "hil_required": False,
        "path_type": "rag_only",
        "spl_generation_status": "none",
        "candidate_spl_present": False,
        "runtime_support_status": "planned",
    }
    shadow = {
        **imperative,
        "spl_generation_status": "approved",
        "candidate_spl_present": True,
    }
    category, _, critical = classify_parity_row(imperative, shadow)
    assert "spl_generation_mismatch" in critical
    failures = validate_check_report(
        {
            "summary": {"expected_minimum_total": 1, "total": 1},
            "rows": [{"row_id": "sim", "critical_mismatch_categories": critical}],
        }
    )
    assert failures


def test_check_passes_on_current_subset_baseline() -> None:
    result = run_dual_parity_eval(limit=12, include_demo=True, include_manual=True)
    assert not result.failures


def test_cli_check_passes_on_subset() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--check",
            "--limit",
            "8",
            "--skip-105",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_parity_side_record_shape() -> None:
    from app.chat.pipeline import build_live_chat_response

    response = build_live_chat_response(ChatRequest(message="Show SOP for failed login investigation"))
    record = parity_side_record(response, side="imperative")
    assert record["side"] == "imperative"
    assert "path_type" in record
    assert "spl_generation_status" in record
    snap = governance_snapshot_from_response(response)
    assert snap["path_type"] == record["path_type"]
