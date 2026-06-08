"""SOC clean-answer evaluation harness tests."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.evals.langgraph_dual_parity import build_parity_index, run_dual_parity_eval
from app.evals.soc_clean_answer_eval import (
    ANSWERS_SCHEMA_VERSION,
    EXPECTED_105_COUNT,
    SCHEMA_VERSION,
    build_answers_report,
    classify_clean_response,
    final_verdict,
    load_eval_rows,
    load_known_manual_questions,
    render_answers_markdown,
    run_clean_answer_eval,
    validate_check_report,
    write_clean_answer_outputs,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_soc_clean_answer_eval.py"
KNOWN_MANUAL_PATH = REPO_ROOT / "docs" / "evals" / "known_manual_soc_questions.json"


def test_loads_all_105_questions() -> None:
    rows = load_eval_rows(include_demo=False, include_manual=False)
    assert len(rows) == EXPECTED_105_COUNT
    assert rows[0]["source"] == "105_map"


def test_loads_known_manual_questions() -> None:
    manual = load_known_manual_questions()
    assert len(manual) >= 7
    payload = json.loads(KNOWN_MANUAL_PATH.read_text(encoding="utf-8"))
    assert payload.get("schema_version")


def test_manual_and_demo_sets_included() -> None:
    rows = load_eval_rows()
    sources = {row["source"] for row in rows}
    assert "105_map" in sources
    assert "demo_scenario" in sources
    assert "manual" in sources
    manual_ids = {row["row_id"] for row in rows if row["source"] == "manual"}
    expected = {item["question_id"] for item in load_known_manual_questions()}
    assert manual_ids == expected
    assert len(rows) >= EXPECTED_105_COUNT + 7


def test_report_schema_valid_on_subset() -> None:
    result = run_clean_answer_eval(limit=5, include_demo=False, include_manual=False)
    report = result.report
    assert report["schema_version"] == SCHEMA_VERSION
    assert "summary" in report
    assert "rows" in report
    assert len(report["rows"]) == 5
    row = report["rows"][0]
    assert "clean_response_status" in row
    assert "violations" in row
    assert "answer_text" in row


def test_check_catches_simulated_mitre_overclaim() -> None:
    meta = {"source": "manual", "mitre_context_only": True}
    record = {
        "mitre_evidence_supported_techniques": ["T1110"],
        "path_type": "rag_only",
        "hil_required": False,
        "answer_text": "T1110 is evidence-supported.",
        "candidate_spl_present": False,
        "spl_status": "none",
        "runtime_support_status": "n/a",
        "mitre_not_claimed_techniques": [],
        "mitre_branch_evidence_supported": ["T1110"],
        "execution_executed": False,
        "llm_fallback_used": False,
        "unsafe_blocked": False,
        "required_evidence_count": 0,
        "missing_evidence_count": 0,
        "analyst_checklist_count": 0,
        "investigation_steps_count": 0,
    }
    status, violations = classify_clean_response(meta, record)
    assert status == "major"
    assert any(v["category"] == "mitre_overclaim_no_context" for v in violations)
    failures = validate_check_report(
        {
            "summary": {
                "include_105": True,
                "base_105_loaded": EXPECTED_105_COUNT,
                "unsafe_execution_flags_enforced": True,
            },
            "rows": [{"row_id": "sim", "source": "manual", "clean_response_status": status, "violations": violations}],
        }
    )
    assert failures


def test_check_catches_simulated_spl_execution_claim() -> None:
    meta = {"source": "105_map"}
    record = {
        "execution_executed": False,
        "answer_text": "The SPL was executed and returned 12 rows.",
        "mitre_evidence_supported_techniques": [],
        "mitre_not_claimed_techniques": [],
        "mitre_branch_evidence_supported": [],
        "candidate_spl_present": False,
        "spl_status": "candidate",
        "llm_fallback_used": False,
        "unsafe_blocked": False,
        "runtime_support_status": "runtime_active",
        "required_evidence_count": 0,
        "missing_evidence_count": 0,
        "analyst_checklist_count": 0,
        "investigation_steps_count": 0,
    }
    status, violations = classify_clean_response(meta, record)
    assert status == "critical"
    assert any(v["category"] == "spl_execution_claim" for v in violations)
    failures = validate_check_report(
        {
            "summary": {
                "include_105": True,
                "base_105_loaded": EXPECTED_105_COUNT,
                "unsafe_execution_flags_enforced": True,
            },
            "rows": [{"row_id": "sim", "source": "105_map", "clean_response_status": status, "violations": violations}],
        }
    )
    assert failures


def test_check_catches_sop_generating_spl() -> None:
    meta = {"source": "manual", "sop_only_no_spl": True}
    record = {
        "candidate_spl_present": True,
        "spl_status": "candidate",
        "answer_text": "Here is the SOP and SPL.",
        "mitre_evidence_supported_techniques": [],
        "mitre_not_claimed_techniques": [],
        "mitre_branch_evidence_supported": [],
        "execution_executed": False,
        "llm_fallback_used": False,
        "unsafe_blocked": False,
        "runtime_support_status": "n/a",
        "required_evidence_count": 0,
        "missing_evidence_count": 0,
        "analyst_checklist_count": 0,
        "investigation_steps_count": 0,
    }
    status, violations = classify_clean_response(meta, record)
    assert status == "major"
    assert any(v["category"] == "sop_generates_spl" for v in violations)


def test_check_catches_unsafe_request_not_blocked() -> None:
    meta = {"source": "manual", "unsafe_must_block": True}
    record = {
        "unsafe_blocked": False,
        "hil_required": False,
        "answer_text": "Locking user and executing SPL.",
        "execution_executed": False,
        "mitre_evidence_supported_techniques": [],
        "mitre_not_claimed_techniques": [],
        "mitre_branch_evidence_supported": [],
        "candidate_spl_present": False,
        "spl_status": "none",
        "llm_fallback_used": False,
        "runtime_support_status": "n/a",
        "required_evidence_count": 0,
        "missing_evidence_count": 0,
        "analyst_checklist_count": 0,
        "investigation_steps_count": 0,
    }
    status, violations = classify_clean_response(meta, record)
    assert status == "critical"
    assert any(v["category"] == "unsafe_request_not_blocked" for v in violations)


def test_baseline_passes_clean_answer_subset_check() -> None:
    result = run_clean_answer_eval(limit=12, include_demo=True, include_manual=True)
    critical_or_major_manual = [
        row
        for row in result.report["rows"]
        if row.get("source") in {"manual", "demo_scenario"}
        and row.get("clean_response_status") in {"critical", "major"}
    ]
    assert not critical_or_major_manual, critical_or_major_manual


def test_no_live_llm_required_for_ci_subset() -> None:
    result = run_clean_answer_eval(limit=8, include_105=False, include_demo=True, include_manual=True)
    assert result.report["profile"]["ai_soc_llm_final_synthesis_enabled"] is False
    assert result.report["profile"]["ai_soc_llm_live_synthesis_enabled"] is False


def test_emit_answers_creates_markdown_and_json(tmp_path: Path) -> None:
    parity = run_dual_parity_eval(limit=3, include_demo=False, include_manual=False)
    parity_index = build_parity_index(parity.report)
    result = run_clean_answer_eval(
        limit=3,
        include_demo=False,
        include_manual=False,
        emit_answers=True,
        include_parity=True,
        parity_index=parity_index,
    )
    answers_json = tmp_path / "answers.json"
    answers_md = tmp_path / "answers.md"
    write_clean_answer_outputs(
        result,
        json_path=tmp_path / "report.json",
        markdown_path=tmp_path / "summary.md",
        answers_json_path=answers_json,
        answers_markdown_path=answers_md,
    )
    assert answers_json.is_file()
    assert answers_md.is_file()
    payload = json.loads(answers_json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == ANSWERS_SCHEMA_VERSION
    assert len(payload["rows"]) == 3
    row = payload["rows"][0]
    assert row.get("query")
    assert "answer_text" in row
    assert row.get("final_verdict") in {"PASS", "REVIEW", "FAIL"}
    assert "parity" in row
    md = answers_md.read_text(encoding="utf-8")
    assert "### Question" in md
    assert "### Full answer text" in md
    assert "### LangGraph parity" in md


def test_answers_report_includes_all_sources_on_full_load() -> None:
    rows = load_eval_rows()
    assert len(rows) >= EXPECTED_105_COUNT + 7


def test_render_answers_contains_expected_actual_fields() -> None:
    report = build_answers_report(
        {
            "generated_at": "t",
            "profile": {},
            "summary": {"total_evaluated": 1, "pass_count": 1, "review_count": 0, "fail_count": 0},
            "rows": [
                {
                    "row_id": "q0.q001",
                    "source": "105_map",
                    "query": "Which hosts failed login?",
                    "expected_use_case_id": None,
                    "expected_path_type": None,
                    "actual_use_case_id": "auth_failed_login_spike",
                    "path_type": "spl_review",
                    "answer_text": "Governed review-only answer.",
                    "violations": [],
                    "final_verdict": "PASS",
                    "clean_response_status": "pass",
                    "duration_ms": 12,
                    "timed_out": False,
                }
            ],
        }
    )
    md = render_answers_markdown(report)
    assert "Which hosts failed login?" in md
    assert "Governed review-only answer." in md
    assert "auth_failed_login_spike" in md
    assert "PASS" in md


def test_timeout_recorded_without_crashing(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.evals.soc_clean_answer_eval as eval_mod

    def _slow_callable(query: str) -> tuple[None, None]:
        time.sleep(0.05)
        return None, None

    monkeypatch.setattr(eval_mod, "_run_chat_eval_callable", _slow_callable)
    result = run_clean_answer_eval(limit=1, include_105=False, include_demo=True, include_manual=False, timeout_seconds=0.001)
    row = result.report["rows"][-1]
    assert row.get("timed_out") is True
    assert row.get("final_verdict") == "REVIEW"
    assert any(v.get("category") == "eval_timeout" for v in row.get("violations") or [])


def test_final_verdict_mapping() -> None:
    assert final_verdict("pass", source="105_map") == "PASS"
    assert final_verdict("display", source="105_map") == "REVIEW"
    assert final_verdict("major", source="manual") == "FAIL"
    assert final_verdict("pass", source="manual", timed_out=True) == "REVIEW"


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
