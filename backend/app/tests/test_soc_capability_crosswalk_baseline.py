"""Phase 0 SOC Capability Crosswalk baseline validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.api.routes_knowledge import export_mapping_artifact
from app.knowledge.mapping_exports import MITRE_METADATA_ROLE

REPO_ROOT = Path(__file__).resolve().parents[3]
CROSSWALK_PATH = REPO_ROOT / "docs" / "evals" / "soc_capability_crosswalk.json"
GENERATOR_PATH = REPO_ROOT / "scripts" / "build_soc_capability_crosswalk.py"

ALLOWED_LIVE_SKILLS = frozenset(
    {"alert_summary", "spl_generation", "attack_discovery", "knowledge_recall"}
)

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "generated_at",
    "row_counts",
    "question_rows",
    "use_case_rows",
    "github_skill_rows",
    "warnings",
}

REQUIRED_ROW_KEYS = {
    "question_id",
    "question",
    "question_match_status",
    "use_case_id",
    "catalog_present",
    "enrichment_present",
    "mapping_status",
    "mapping_confidence",
    "live_execution_skill",
    "planning_or_analytic_skill",
    "github_reference_skills",
    "github_reuse_type",
    "spl_template_id",
    "spl_template_status",
    "mitre_metadata_role",
    "mitre_candidates",
    "mitre_blocked",
    "evidence_requirements",
    "investigation_workflow_status",
    "answer_rules_status",
    "rag_status",
    "runtime_support_status",
    "validation_status",
    "tests_added",
}


@pytest.fixture(scope="module")
def crosswalk() -> dict:
    assert CROSSWALK_PATH.is_file(), "soc_capability_crosswalk.json missing; run generator"
    payload = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_crosswalk_file_exists_with_schema(crosswalk: dict) -> None:
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(crosswalk.keys())
    assert crosswalk["row_counts"]["question_rows"] == 105
    assert crosswalk["row_counts"]["use_case_rows"] == 50
    assert crosswalk["row_counts"]["github_skill_rows"] == 12
    assert crosswalk["row_counts"]["catalog_use_cases"] == 47
    assert crosswalk["row_counts"]["enrichment_records"] == 12
    assert crosswalk["row_counts"]["enrichment_only_use_cases"] == 3


def test_question_and_use_case_rows_have_required_fields(crosswalk: dict) -> None:
    for row in crosswalk["question_rows"]:
        assert REQUIRED_ROW_KEYS.issubset(row.keys()), row.get("question_id")
    for row in crosswalk["use_case_rows"]:
        assert REQUIRED_ROW_KEYS.issubset(row.keys()), row.get("use_case_id")
        assert row["question_match_status"] == "n/a_use_case_only"
        assert row["question_id"] is None


def test_all_live_execution_skills_are_allowed_enum(crosswalk: dict) -> None:
    for section in ("question_rows", "use_case_rows"):
        for row in crosswalk[section]:
            skill = row.get("live_execution_skill")
            if skill is not None:
                assert skill in ALLOWED_LIVE_SKILLS, (section, row.get("question_id"), skill)


def test_no_enrichment_only_runtime_active(crosswalk: dict) -> None:
    for row in crosswalk["use_case_rows"]:
        if row.get("catalog_present") is False and row.get("enrichment_present") is True:
            assert row["runtime_support_status"] != "runtime_active"


def test_no_github_skill_runtime_active(crosswalk: dict) -> None:
    for row in crosswalk["github_skill_rows"]:
        assert row["runtime_support_status"] != "runtime_active"
        assert row.get("runtime_skill") is False


def test_github_skills_map_to_use_cases_or_state(crosswalk: dict) -> None:
    for row in crosswalk["github_skill_rows"]:
        mapped_ids = row.get("mapped_use_case_ids") or []
        mapping_state = row.get("mapping_state")
        assert mapped_ids or mapping_state in {"deferred", "rejected", "mapped"}


def test_runtime_active_rows_satisfy_activation_rules(crosswalk: dict) -> None:
    for section in ("question_rows", "use_case_rows"):
        for row in crosswalk[section]:
            if row.get("runtime_support_status") != "runtime_active":
                continue
            assert row.get("catalog_present") is True
            assert row.get("validation_status") in {"soc_approved", "tests_added"}
            assert row.get("tests_added") is True
            assert row.get("live_execution_skill") in ALLOWED_LIVE_SKILLS
            assert row.get("spl_template_status") in {"active", "sop_only"}


def test_mitre_metadata_role_when_candidates_present(crosswalk: dict) -> None:
    for section in ("question_rows", "use_case_rows"):
        for row in crosswalk[section]:
            if row.get("mitre_candidates"):
                assert row.get("mitre_metadata_role") == MITRE_METADATA_ROLE


def test_knowledge_export_includes_soc_capability_crosswalk() -> None:
    response = export_mapping_artifact("soc_capability_crosswalk", file_format="json")
    payload = json.loads(response.body)

    assert payload["artifact"] == "soc_capability_crosswalk"
    assert payload["row_counts"]["question_rows"] == 105
    assert payload["row_counts"]["use_case_rows"] == 50
    assert payload["row_counts"]["github_skill_rows"] == 12
    assert len(payload["question_rows"]) == 105
    assert payload["mitre_metadata_role"] == MITRE_METADATA_ROLE


def test_knowledge_export_csv_includes_row_kinds() -> None:
    response = export_mapping_artifact("crosswalk", file_format="csv")
    body = response.body.decode("utf-8")
    assert "row_kind" in body.splitlines()[0]
    assert body.count("\n") >= 105 + 49 + 7


def test_generator_is_not_imported_by_runtime_chat_path() -> None:
    chat_routes = (REPO_ROOT / "backend" / "app" / "api" / "routes_chat.py").read_text(encoding="utf-8")
    assert "build_soc_capability_crosswalk" not in chat_routes
    assert "soc_capability_crosswalk" not in chat_routes


def test_generator_check_matches_committed_artifact() -> None:
    spec = importlib.util.spec_from_file_location("build_soc_capability_crosswalk", GENERATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    warnings: list[str] = []
    generated = module.generate_crosswalk(warnings)
    committed = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    assert generated["row_counts"] == committed["row_counts"]
    assert len(generated["question_rows"]) == len(committed["question_rows"])
    assert len(generated["use_case_rows"]) == len(committed["use_case_rows"])
    assert len(generated["github_skill_rows"]) == len(committed["github_skill_rows"])
