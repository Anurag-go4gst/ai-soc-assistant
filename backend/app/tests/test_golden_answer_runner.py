from __future__ import annotations

import json
from pathlib import Path

from app.evals.golden_answer_runner import assert_case
from app.evals.golden_answer_runner import main
from app.evals.golden_answer_runner import render_markdown
from app.evals.golden_answer_runner import summarize
from app.evals.golden_answers.schema import load_jsonl_cases
from app.evals.golden_answers.schema import parse_golden_case


def _minimal_response() -> dict[str, object]:
    spl = "search index=pgcil_soc sourcetype=aws:cloudtrail | head 100"
    return {
        "message": "Governed SPL draft ready. It has passed deterministic validation and has not been executed.",
        "selected_skill": "attack_discovery",
        "selected_use_case": {"use_case_id": "aws_security_group_modifications"},
        "evidence_plan": {"answer_mode": "live_investigation", "needs_spl": True},
        "response_mode": "spl_candidate",
        "route_adjudication": {"final_route": "attack_discovery", "authority_source": "route_plan"},
        "query_to_intent": {"intent_classification": {"intent_family": "spl_generation", "answer_goal": ["spl_artifact"]}},
        "candidate_spl": {"generation_mode": "deterministic_template_render", "candidate_spl": spl},
        "spl_validation": {"approved": True, "normalized_spl": spl, "reject_reasons": []},
        "execution": {"status": "skipped", "block_reason": "mcp_not_allowed_by_evidence_plan", "executed_spl": None},
        "human_review": {"required": False},
        "mitre_decision": {"answer_visible": False, "rejected_techniques": []},
        "mitre_mappings": [],
        "analyst_response": {
            "response_profile": "spl_only",
            "spl_code": spl,
            "retrieved_playbook": None,
            "recommended_actions": [],
            "mitre_mappings": [],
            "not_claimed": [],
        },
    }


def test_loads_tier0_jsonl_cases() -> None:
    path = Path(__file__).resolve().parents[1] / "evals" / "golden_answers" / "tier0_control_plane.jsonl"
    cases = load_jsonl_cases([path])

    assert len(cases) == 7
    assert {case.tier for case in cases} == {0}
    assert all(case.source == "control_plane_critical_flow" for case in cases)
    assert any(case.case_id == "tier0.aws_security_group_modifications_spl_only" for case in cases)


def test_assertion_engine_passes_structured_authority_fields() -> None:
    case = parse_golden_case(
        {
            "case_id": "unit.aws",
            "tier": 0,
            "source": "control_plane_critical_flow",
            "query": "Write SPL to determine who made modifications to any AWS security groups",
            "category": "spl_candidate",
            "expected": {
                "selected_skill": "attack_discovery",
                "selected_use_case_id": "aws_security_group_modifications",
                "candidate_spl": {
                    "required": True,
                    "approved": True,
                    "generation_mode": "deterministic_template_render",
                    "must_include": ["index=pgcil_soc", "sourcetype=aws:cloudtrail"],
                    "must_not_include": ["datamodel=", "tstats"],
                },
                "execution": {
                    "expected_status": "skipped",
                    "block_reason": "mcp_not_allowed_by_evidence_plan",
                    "executed_spl_absent": True,
                },
                "analyst_response": {
                    "response_profile": "spl_only",
                    "spl_code_matches_normalized": True,
                },
                "answer_text": {
                    "exact": "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
                },
                "json_path_equals": [{"path": "evidence_plan.needs_spl", "value": True}],
            },
        }
    )

    result = assert_case(case, _minimal_response())

    assert result.passed is True
    assert result.failures == []
    assert result.observed["selected_use_case_id"] == "aws_security_group_modifications"


def test_assertion_engine_reports_clear_failures() -> None:
    case = parse_golden_case(
        {
            "case_id": "unit.bad",
            "tier": 0,
            "source": "control_plane_critical_flow",
            "query": "question",
            "category": "spl_candidate",
            "expected": {
                "selected_use_case_id": "different_case",
                "candidate_spl": {"required": True, "approved": False, "must_include": ["not-present"]},
            },
        }
    )

    result = assert_case(case, _minimal_response())

    assert result.passed is False
    failure_paths = {failure.path for failure in result.failures}
    assert "selected_use_case_id" in failure_paths
    assert "spl_validation.approved" in failure_paths
    assert "spl_validation.normalized_spl" in failure_paths


def test_report_rendering_includes_category_and_failure_counts() -> None:
    case = parse_golden_case(
        {
            "case_id": "unit.bad",
            "tier": 0,
            "source": "control_plane_critical_flow",
            "query": "question",
            "category": "spl_candidate",
            "expected": {"selected_use_case_id": "different_case"},
        }
    )
    result = assert_case(case, _minimal_response())
    summary = summarize([result], case_files=[Path("cases.jsonl")])

    assert summary.overall_pass is False
    assert summary.by_tier["0"]["failed"] == 1
    assert summary.by_category["spl_candidate"]["failed"] == 1
    markdown = render_markdown(summary)
    assert "`unit.bad`" in markdown
    assert "selected_use_case_id" in markdown


def test_main_writes_json_and_markdown_reports_with_stubbed_runner(tmp_path, monkeypatch) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "tier0_stub.jsonl").write_text(
        json.dumps(
            {
                "case_id": "unit.stub",
                "tier": 0,
                "source": "control_plane_critical_flow",
                "query": "question",
                "category": "answer",
                "expected": {"selected_skill": "attack_discovery"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.evals.golden_answer_runner.discover_case_files",
        lambda *, tier=None, all_cases=False, case_dir=case_dir: [case_dir / "tier0_stub.jsonl"],
    )
    monkeypatch.setattr(
        "app.evals.golden_answer_runner.run_case",
        lambda case: assert_case(case, _minimal_response()),
    )
    report_json = tmp_path / "golden.json"
    report_md = tmp_path / "golden.md"

    code = main(
        [
            "--tier",
            "0",
            "--json",
            "--case-dir",
            str(case_dir),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_md),
        ]
    )

    assert code == 0
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["overall_pass"] is True
    assert payload["results"][0]["case_id"] == "unit.stub"
    assert "Golden Answer Evaluation" in report_md.read_text(encoding="utf-8")

