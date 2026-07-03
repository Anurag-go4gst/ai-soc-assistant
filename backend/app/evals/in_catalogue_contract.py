"""In-catalogue (105/50) answer-contract invariant capture and guard (plan 0.3)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.api.routes_chat import chat
from app.chat.answer_shape_router import classify_answer_shape
from app.coverage.question_runtime_map import (
    list_cisco_question_runtime_entries,
    list_question_runtime_entries,
)
from app.evals.golden_answer_runner import _model_to_dict
from app.evals.sentinel_eval import sentinel_runtime
from app.schemas.requests import ChatRequest

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "in_catalogue_contract"
BASELINE_PATH = FIXTURE_DIR / "baseline.json"
SCHEMA_VERSION = 1

CONTRACT_FIELDS = (
    "match_path",
    "mapped_question_ref",
    "route",
    "answer_shape",
    "severity_label",
    "mitre_answer_visible",
    "mitre_technique_ids",
    "execution_eligible",
    "execution_status",
    "contract_answer_mode",
    "enabled_sections",
    "analyst_enabled_sections",
    "human_review_required",
    "spl_approved",
)


def iter_in_catalogue_entries() -> list[dict[str, Any]]:
    """105 exact map rows + Cisco 50 catalogue rows."""
    entries: list[dict[str, Any]] = []
    for row in list_question_runtime_entries():
        entries.append(
            {
                "catalogue": "105",
                "question_ref": row.get("question_ref") or row.get("question_id"),
                "question": row.get("question_text") or row.get("question"),
            }
        )
    for row in list_cisco_question_runtime_entries():
        entries.append(
            {
                "catalogue": "cisco50",
                "question_ref": row.get("question_ref") or row.get("question_id"),
                "question": row.get("question_text") or row.get("question"),
            }
        )
    return entries


def capture_contract_row(question: str) -> dict[str, Any]:
    with sentinel_runtime():
        response = chat(ChatRequest(message=question, session_id=f"icc-{uuid.uuid4()}"))
    payload = _model_to_dict(response)

    query_to_intent = payload.get("query_to_intent") or {}
    candidate_mappings = query_to_intent.get("candidate_mappings") or {}
    evidence_plan = payload.get("evidence_plan") or {}
    severity_decision = payload.get("severity_decision") or {}
    execution = payload.get("execution") or {}
    spl_validation = payload.get("spl_validation") or {}
    candidate_spl = payload.get("candidate_spl") or {}
    answer_contract = payload.get("answer_contract") or {}
    render_sections = answer_contract.get("render_sections") or {}
    analyst_response = payload.get("analyst_response") or {}
    analyst_sections = analyst_response.get("render_sections") or {}

    return {
        "match_path": candidate_mappings.get("match_path"),
        "mapped_question_ref": candidate_mappings.get("question_ref"),
        "route": payload.get("selected_skill"),
        "answer_shape": classify_answer_shape(question).primary_shape,
        "severity_label": severity_decision.get("severity_label") if isinstance(severity_decision, dict) else None,
        "execution_status": execution.get("status"),
        "execution_eligible": candidate_spl.get("execution_eligible"),
        "spl_approved": spl_validation.get("approved"),
        "human_review_required": answer_contract.get("human_review_required"),
        "contract_answer_mode": answer_contract.get("answer_mode") or evidence_plan.get("answer_mode"),
        "enabled_sections": sorted(name for name, enabled in render_sections.items() if enabled),
        "analyst_enabled_sections": sorted(name for name, enabled in analyst_sections.items() if enabled),
        "mitre_answer_visible": answer_contract.get("mitre_answer_visible"),
        "mitre_technique_ids": sorted(answer_contract.get("mitre_technique_ids") or []),
    }


def capture_all(entries: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    entries = entries if entries is not None else iter_in_catalogue_entries()
    rows: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = f"{entry['catalogue']}:{entry['question_ref']}"
        try:
            rows[key] = capture_contract_row(str(entry["question"]))
        except Exception as exc:
            rows[key] = {"error": f"{type(exc).__name__}: {exc}"}
    return rows


def freeze_baseline(rows: dict[str, dict[str, Any]], path: Path = BASELINE_PATH) -> list[str]:
    errors = [key for key, row in rows.items() if "error" in row]
    if errors:
        return errors
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "note": "Frozen in-catalogue contract invariants (105 + Cisco 50). Regenerate via scripts/capture_in_catalogue_contract_fixtures.py --freeze",
        "question_count": len(rows),
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return []


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["rows"]


def assert_execution_never_eligible(row: dict[str, Any]) -> list[str]:
    if row.get("execution_eligible") is True:
        return ["execution_eligible_must_stay_false"]
    return []


def compare_row(key: str, expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    if "error" in actual:
        return [f"{key}: pipeline error {actual['error']}"]
    diffs: list[str] = []
    diffs.extend(assert_execution_never_eligible(actual))
    for field in CONTRACT_FIELDS:
        if expected.get(field) != actual.get(field):
            diffs.append(f"{key}.{field}: expected={expected.get(field)!r} actual={actual.get(field)!r}")
    return diffs


def check_against_baseline(
    rows: dict[str, dict[str, Any]],
    path: Path = BASELINE_PATH,
) -> list[str]:
    if not path.is_file():
        return [f"baseline missing: {path}"]
    expected_rows = load_baseline(path)
    diffs: list[str] = []
    for key in sorted(set(expected_rows) | set(rows)):
        expected = expected_rows.get(key)
        actual = rows.get(key)
        if expected is None or actual is None:
            diffs.append(f"{key}: catalogue set changed without re-freeze")
            continue
        diffs.extend(compare_row(key, expected, actual))
    return diffs
