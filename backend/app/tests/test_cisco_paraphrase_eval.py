from __future__ import annotations

import json
from pathlib import Path

from app.query_understanding.parser import understand_query


def test_cisco_paraphrase_rows_route_to_expected_catalogue_entries() -> None:
    path = Path(__file__).resolve().parents[3] / "docs" / "evals" / "cisco_paraphrase_eval_rows.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["rows"]
    assert rows

    for row in rows:
        result = understand_query(row["query"])
        assert result.mapped_question_ref == row["expected_question_id"], row["case_id"]
        assert result.mapped_pattern_type == row["expected_pattern_type"], row["case_id"]
        assert row["expected_path_type"] in {"review_only_spl", "metadata_hygiene"}
