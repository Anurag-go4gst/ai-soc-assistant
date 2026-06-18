from __future__ import annotations

import json
from pathlib import Path


def test_cisco_question_bank_has_50_unique_rows_with_required_fields() -> None:
    bank_path = Path(__file__).resolve().parents[3] / "docs" / "evals" / "cisco_powergrid_question_bank.json"
    payload = json.loads(bank_path.read_text())
    entries = payload["entries"]
    assert payload["question_count"] == 50
    assert len(entries) == 50
    ids = [entry["question_id"] for entry in entries]
    assert len(set(ids)) == 50
    required = {
        "question_id",
        "segment",
        "template_wave",
        "eval_gate_min_wave",
        "question",
        "expected_path_type",
        "expected_pattern_type",
        "required_kb_slots",
        "mcp_tool_sequence",
        "spl_policy_tier",
        "safety_expectations",
    }
    for entry in entries:
        assert required.issubset(entry), entry.get("question_id")
        assert entry["question"].strip()
