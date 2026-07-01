"""Phase 10 SOC/COE validation package baseline.

Validation and documentation artifacts only — asserts the generated review
sheets exist, are crosswalk-derived, surface (never fabricate) governance
status, and are exposed as read-only Knowledge exports. No runtime behavior.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes_knowledge import export_mapping_artifact
from app.knowledge.mapping_exports import MITRE_METADATA_ROLE, SOC_VALIDATION_ARTIFACTS

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_DIR = REPO_ROOT / "docs" / "validation"
GENERATOR_PATH = REPO_ROOT / "scripts" / "build_soc_validation_sheets.py"

ALLOWED_LIVE_SKILLS = frozenset(
    {"alert_summary", "spl_generation", "attack_discovery", "knowledge_recall"}
)

EXPECTED_FILES = {
    "use_case_validation_sheet.json",
    "spl_template_review_sheet.json",
    "mitre_validation_sheet.json",
    "question_validation_sheet.json",
    "github_enrichment_review_sheet.json",
    "github_batch_intake_sheet.json",
    "rag_sop_validation_sheet.json",
    "pending_skill_enrichment_backlog_sheet.json",
    "combination_matrix_sheet.json",
    "demo_scenario_sheet.json",
}


def _load_generator():
    spec = importlib.util.spec_from_file_location("build_soc_validation_sheets", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sheet(name: str) -> dict:
    return json.loads((VALIDATION_DIR / name).read_text(encoding="utf-8"))


def test_generator_runs_and_is_not_stale() -> None:
    module = _load_generator()
    sheets, readme, _warnings = module.generate_sheets()
    assert set(module.FILE_MAP) == EXPECTED_FILES
    assert readme.startswith("# SOC / COE Validation Package")
    # On-disk artifacts must match generated output (deterministic --check).
    assert module.main(["--check"]) == 0
    assert sheets  # generation produced payloads


def test_all_expected_artifacts_exist() -> None:
    assert (VALIDATION_DIR / "README.md").is_file()
    for name in EXPECTED_FILES:
        assert (VALIDATION_DIR / name).is_file(), name


def test_use_case_sheet_has_all_catalog_rows() -> None:
    sheet = _sheet("use_case_validation_sheet.json")
    assert sheet["row_counts"]["use_cases"] == 64
    assert len(sheet["rows"]) == 64


def test_question_sheet_has_all_105_rows() -> None:
    sheet = _sheet("question_validation_sheet.json")
    assert sheet["row_counts"]["questions"] == 105
    assert len(sheet["rows"]) == 105


def test_github_sheet_has_all_12_rows() -> None:
    sheet = _sheet("github_enrichment_review_sheet.json")
    assert sheet["row_counts"]["github_skills"] == 12
    assert len(sheet["rows"]) == 12


def test_runtime_active_rows_satisfy_freeze_gate_2() -> None:
    rows = _sheet("use_case_validation_sheet.json")["rows"]
    active = [r for r in rows if r["runtime_support_status"] == "runtime_active"]
    assert active  # there are runtime_active pilots
    for row in active:
        assert row["catalog_present"] is True
        assert row["live_execution_skill"] in ALLOWED_LIVE_SKILLS
        assert row["spl_template_status"] in {"active", "sop_only"}
        assert row["tests_added"] is True
        assert row["validation_status"] in {"soc_approved", "tests_added"}


def test_enrichment_only_rows_are_not_runtime_active() -> None:
    rows = _sheet("use_case_validation_sheet.json")["rows"]
    for row in rows:
        if row["enrichment_present"] and not row["catalog_present"]:
            assert row["runtime_support_status"] != "runtime_active"


def test_github_rows_are_not_runtime_active() -> None:
    rows = _sheet("github_enrichment_review_sheet.json")["rows"]
    for row in rows:
        assert row["runtime_support_status"] != "runtime_active"
        assert row["runtime_skill"] is False


def test_mitre_sheet_labels_metadata_not_evidence() -> None:
    sheet = _sheet("mitre_validation_sheet.json")
    assert sheet["mitre_metadata_role"] == MITRE_METADATA_ROLE
    for row in sheet["rows"]:
        assert row["mitre_metadata_role"] == MITRE_METADATA_ROLE


def test_spl_sheet_is_review_only_no_execution() -> None:
    rows = _sheet("spl_template_review_sheet.json")["rows"]
    assert rows
    for row in rows:
        assert row["review_only"] is True
        assert row["no_execution"] is True


def test_demo_scenario_sheet_exists_and_does_not_overclaim() -> None:
    sheet = _sheet("demo_scenario_sheet.json")
    assert sheet["row_counts"]["scenarios"] >= 1
    pilot = next(
        (r for r in sheet["rows"] if r["target_use_case_id"] == "email_phishing_header_review"),
        None,
    )
    assert pilot is not None
    # enrichment-only pilot must not be presented as live-supported.
    assert pilot["demo_safe_as_live"] is False


def test_review_decision_fields_are_blank_not_pre_approved() -> None:
    rows = _sheet("use_case_validation_sheet.json")["rows"]
    assert all(row["review_decision"] == "" for row in rows)
    mitre = _sheet("mitre_validation_sheet.json")["rows"]
    assert all(row["soc_review_notes"] == "" for row in mitre)


@pytest.mark.parametrize("artifact", sorted(SOC_VALIDATION_ARTIFACTS))
def test_knowledge_exports_are_artifact_backed(artifact: str) -> None:
    response = export_mapping_artifact(artifact, file_format="json")
    payload = json.loads(response.body)
    assert payload["artifact"] == artifact
    assert payload["export_kind"] == "json_backed"
    assert payload["source_file"].startswith("docs/validation/")
    assert isinstance(payload["rows"], list)
    assert "attachment" in response.headers["content-disposition"]


def test_knowledge_export_csv_for_flat_sheet() -> None:
    response = export_mapping_artifact("soc_validation_use_cases", file_format="csv")
    rows = list(csv.DictReader(io.StringIO(response.body.decode("utf-8"))))
    assert len(rows) == 64
    assert "use_case_id" in rows[0]
    assert "runtime_support_status" in rows[0]


def test_knowledge_export_nested_sheet_rejects_csv() -> None:
    with pytest.raises(HTTPException) as exc:
        export_mapping_artifact("soc_validation_demo_scenarios", file_format="csv")
    assert exc.value.status_code == 400
