"""Read-only mapping export endpoints for analyst review."""

from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi import HTTPException

from app.api.routes_knowledge import export_mapping_artifact
from app.knowledge.mapping_exports import MITRE_METADATA_ROLE, SOC_VALIDATION_ARTIFACTS


def test_detection_coverage_endpoint() -> None:
    from app.api.routes_knowledge import knowledge_detection_coverage

    payload = knowledge_detection_coverage()
    assert payload["schema_role"] == "detection_coverage_v1"
    assert payload["covered_count"] + payload["gap_count"] == payload["technique_count"]


def test_mapping_summary_endpoint_matches_crosswalk() -> None:
    from app.knowledge.mapping_exports import build_mapping_summary, build_soc_capability_crosswalk_export_payload

    summary = build_mapping_summary()
    crosswalk = build_soc_capability_crosswalk_export_payload()

    assert summary["row_counts"]["question_rows"] == 105
    assert summary["row_counts"]["use_case_rows"] == 45
    assert summary["row_counts"]["enrichment_records"] == 13
    assert summary["live_route_skills"] == list(
        ("alert_summary", "spl_generation", "attack_discovery", "knowledge_recall", "guided_investigation")
    )
    assert summary["allowed_live_execution_skills"] == crosswalk["allowed_live_execution_skills"]
    assert sum(summary["question_skill_distribution"].values()) == 105


def test_question_runtime_map_json_export_contains_105_rows() -> None:
    response = export_mapping_artifact("question_runtime_map", file_format="json")
    payload = json.loads(response.body)

    assert payload["artifact"] == "question_runtime_map"
    assert payload["export_kind"] == "legacy_base"
    assert payload["mitre_metadata_role"] == MITRE_METADATA_ROLE
    assert payload["row_count"] == 105
    assert len(payload["rows"]) == 105
    assert "attachment" in response.headers["content-disposition"]


def test_question_runtime_map_csv_export_is_excel_friendly() -> None:
    response = export_mapping_artifact("105_questions", file_format="csv")
    rows = list(csv.DictReader(io.StringIO(response.body.decode("utf-8"))))

    assert len(rows) == 105
    assert rows[0]["question_ref"].startswith("q0.q")
    assert "mitre_registry_permitted" in rows[0]
    assert rows[0]["mitre_metadata_role"] == MITRE_METADATA_ROLE
    assert response.media_type == "text/csv"


def test_use_case_catalog_exports_current_catalog_rows() -> None:
    response = export_mapping_artifact("use_case_catalog", file_format="json")
    payload = json.loads(response.body)

    assert payload["artifact"] == "use_case_catalog"
    assert payload["export_kind"] == "catalog_with_enrichment_join"
    assert payload["mitre_metadata_role"] == MITRE_METADATA_ROLE
    assert payload["row_count"] >= 42
    auth = next(row for row in payload["rows"] if row["use_case_id"] == "auth_failed_login_spike")
    assert auth.get("enrichment_present") is True
    assert auth.get("domain")
    assert auth.get("spl_template_status") == "active"
    registry = auth.get("mitre_registry")
    assert isinstance(registry, dict)
    assert registry.get("candidate") or registry.get("permitted") or registry.get("blocked")


def test_use_case_catalog_csv_preserves_mitre_registry() -> None:
    response = export_mapping_artifact("use_case_catalog", file_format="csv")
    rows = list(csv.DictReader(io.StringIO(response.body.decode("utf-8"))))
    auth = next(row for row in rows if row["use_case_id"] == "auth_failed_login_spike")

    assert auth["mitre_registry_candidate"] or auth["mitre_registry_permitted"] or auth["mitre_registry_blocked"]
    assert auth["domain"] == "identity-access-management"
    assert auth["spl_template_status"] == "active"
    assert auth["enrichment_present"] == "True"
    assert auth["mitre_metadata_role"] == MITRE_METADATA_ROLE


def test_use_case_catalog_includes_enrichment_only_pilots() -> None:
    response = export_mapping_artifact("use_case_catalog", file_format="json")
    payload = json.loads(response.body)
    ids = {row["use_case_id"] for row in payload["rows"]}

    assert "email_phishing_header_review" in ids
    pilot = next(row for row in payload["rows"] if row["use_case_id"] == "email_phishing_header_review")
    assert pilot.get("catalog_present") is False
    assert pilot.get("enrichment_present") is True


def test_soc_capability_crosswalk_json_export_contains_expected_rows() -> None:
    response = export_mapping_artifact("soc_capability_crosswalk", file_format="json")
    payload = json.loads(response.body)

    assert payload["artifact"] == "soc_capability_crosswalk"
    assert payload["row_counts"]["question_rows"] == 105
    assert payload["row_counts"]["use_case_rows"] == 45
    assert payload["row_counts"]["enrichment_records"] == 13
    assert payload["mitre_metadata_role"] == MITRE_METADATA_ROLE


def test_skill_coverage_matrix_json_export_contains_105_rows() -> None:
    response = export_mapping_artifact("skill_coverage_matrix", file_format="json")
    payload = json.loads(response.body)

    assert payload["artifact"] == "skill_coverage_matrix"
    assert payload["row_count"] == 105
    assert len(payload["rows"]) == 105
    assert payload["mitre_metadata_role"] == MITRE_METADATA_ROLE


def test_skill_coverage_matrix_csv_includes_mapping_and_metadata_role() -> None:
    response = export_mapping_artifact("coverage_matrix", file_format="csv")
    rows = list(csv.DictReader(io.StringIO(response.body.decode("utf-8"))))

    assert len(rows) == 105
    assert "mapping_status" in rows[0]
    assert rows[0]["mitre_metadata_role"] == MITRE_METADATA_ROLE
    q062 = next(row for row in rows if row["question_id"] == "q0.q062")
    assert q062["mapping_status"] == "curated_manual"
    assert q062["use_case_id"] == "auth_failed_login_spike"


@pytest.mark.parametrize(
    "artifact",
    [
        "github_skill_intake_register",
        "github_skill_discovery_index",
        "github_skill_triage_scores",
        "proposed_use_cases_from_github",
        "skill_enrichment_status_matrix",
        "rejected_github_skills",
        "pending_skill_enrichment_backlog",
    ],
)
def test_retired_github_factory_exports_are_removed(artifact: str) -> None:
    with pytest.raises(HTTPException) as exc:
        export_mapping_artifact(artifact, file_format="json")
    assert exc.value.status_code == 404


def test_soc_validation_exports_cover_all_phase10_artifacts() -> None:
    expected = {
        "soc_validation_use_cases",
        "soc_validation_spl_templates",
        "soc_validation_mitre",
        "soc_validation_questions",
        "soc_validation_rag_sop",
        "soc_validation_combination_matrix",
        "soc_validation_demo_scenarios",
    }
    assert set(SOC_VALIDATION_ARTIFACTS) == expected


@pytest.mark.parametrize("artifact", sorted(SOC_VALIDATION_ARTIFACTS))
def test_soc_validation_json_exports(artifact: str) -> None:
    response = export_mapping_artifact(artifact, file_format="json")
    payload = json.loads(response.body)
    assert payload["artifact"] == artifact
    assert payload["export_kind"] == "json_backed"
    assert len(payload["rows"]) >= 1


def test_soc_validation_combination_matrix_has_eight_cases() -> None:
    response = export_mapping_artifact("soc_validation_combination_matrix", file_format="json")
    payload = json.loads(response.body)
    assert payload["row_counts"]["cases"] == 8
    codes = {row["case"] for row in payload["rows"]}
    assert codes == {"A", "B", "C", "D", "E", "F", "G", "H"}
