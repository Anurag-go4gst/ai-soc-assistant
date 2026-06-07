"""Read-only mapping export endpoints for analyst review."""

from __future__ import annotations

import csv
import io
import json

from app.api.routes_knowledge import export_mapping_artifact


def test_question_runtime_map_json_export_contains_105_rows() -> None:
    response = export_mapping_artifact("question_runtime_map", file_format="json")
    payload = json.loads(response.body)

    assert payload["artifact"] == "question_runtime_map"
    assert payload["row_count"] == 105
    assert len(payload["rows"]) == 105
    assert "attachment" in response.headers["content-disposition"]


def test_question_runtime_map_csv_export_is_excel_friendly() -> None:
    response = export_mapping_artifact("105_questions", file_format="csv")
    rows = list(csv.DictReader(io.StringIO(response.body.decode("utf-8"))))

    assert len(rows) == 105
    assert rows[0]["question_ref"].startswith("q0.q")
    assert "mitre_registry_permitted" in rows[0]
    assert response.media_type == "text/csv"


def test_use_case_catalog_exports_current_catalog_rows() -> None:
    response = export_mapping_artifact("use_case_catalog", file_format="json")
    payload = json.loads(response.body)

    assert payload["artifact"] == "use_case_catalog"
    assert payload["row_count"] >= 42
    assert any(row["use_case_id"] == "auth_failed_login_spike" for row in payload["rows"])

