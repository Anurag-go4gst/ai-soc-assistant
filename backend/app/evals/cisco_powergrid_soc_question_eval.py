"""Deterministic Cisco power-grid question-bank eval.

This eval is intentionally offline: it validates catalogue wiring, phased gate
semantics, review-only SPL draft availability, and metadata-only posture without
requiring a running backend or Splunk.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.coverage.question_runtime_map import match_question_runtime_entry
from app.query_understanding.parser import understand_query
from app.spl.draft_preview import build_draft_preview
from app.config import settings

WAVE_ORDER = {
    "batch1": 0,
    "batch2_metadata": 1,
    "wave1": 2,
    "wave2": 3,
    "wave3": 4,
}


@dataclass(frozen=True)
class CiscoEvalResult:
    question_id: str
    status: str
    reason: str
    critical_violations: list[str]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "status": self.status,
            "reason": self.reason,
            "critical_violations": list(self.critical_violations),
            "details": self.details,
        }


def load_question_bank(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Cisco question bank must contain entries[]")
    return [entry for entry in entries if isinstance(entry, dict)]


def _wave_due(row: dict[str, Any], min_wave: str) -> bool:
    gate = str(row.get("eval_gate_min_wave") or "wave3")
    return WAVE_ORDER.get(gate, 99) <= WAVE_ORDER[min_wave]


def evaluate_row(row: dict[str, Any], *, min_wave: str) -> CiscoEvalResult:
    qid = str(row.get("question_id") or "")
    question = str(row.get("question") or "")
    critical: list[str] = []
    if not qid or not question:
        return CiscoEvalResult(qid or "missing", "FAIL", "schema_missing_id_or_question", ["schema"], {})
    match = match_question_runtime_entry(question)
    qu = understand_query(question)
    if not match or match.get("question_id") != qid:
        critical.append("runtime_map_exact_match_missing")
    if getattr(qu, "mapped_pattern_type", None) != row.get("expected_pattern_type"):
        critical.append("pattern_type_mismatch")
    tier = str(row.get("spl_policy_tier") or "")
    details: dict[str, Any] = {
        "mapped_pattern_type": getattr(qu, "mapped_pattern_type", None),
        "mapped_question_ref": getattr(qu, "mapped_question_ref", None),
        "spl_policy_tier": tier,
        "due": _wave_due(row, min_wave),
    }
    if tier == "metadata_only":
        if row.get("mcp_tool_sequence") and "splunk_run_query" in row["mcp_tool_sequence"]:
            critical.append("metadata_row_uses_run_query")
        details["metadata_hygiene"] = {
            "needs_spl": False,
            "execution_enabled": False,
            "planned_tools": row.get("mcp_tool_sequence") or [],
        }
    else:
        preview = build_draft_preview(question, pattern_type=str(row.get("expected_pattern_type") or ""))
        if _wave_due(row, min_wave) and preview is None:
            critical.append("missing_review_draft_preview")
        if preview:
            details["draft_family"] = preview.get("detection_family")
            if preview.get("execution_eligible"):
                critical.append("draft_marked_execution_eligible")
    if not _wave_due(row, min_wave):
        status = "REVIEW"
        reason = "wave_deferred"
    elif critical:
        status = "FAIL"
        reason = "critical_violations"
    else:
        status = "PASS"
        reason = "happy_path"
    return CiscoEvalResult(qid, status, reason, critical, details)


def run_cisco_eval(bank_path: Path, *, min_wave: str = "wave3", question_id: str | None = None) -> dict[str, Any]:
    if min_wave not in WAVE_ORDER:
        raise ValueError(f"unknown min_wave: {min_wave}")
    rows = load_question_bank(bank_path)
    if question_id:
        rows = [row for row in rows if row.get("question_id") == question_id]
    original_draft_preview = settings.ai_soc_spl_draft_preview_enabled
    settings.ai_soc_spl_draft_preview_enabled = True
    try:
        results = [evaluate_row(row, min_wave=min_wave).to_dict() for row in rows]
    finally:
        settings.ai_soc_spl_draft_preview_enabled = original_draft_preview
    return {
        "bank_path": str(bank_path),
        "min_wave": min_wave,
        "question_id": question_id,
        "total": len(results),
        "pass": sum(1 for item in results if item["status"] == "PASS"),
        "review": sum(1 for item in results if item["status"] == "REVIEW"),
        "fail": sum(1 for item in results if item["status"] == "FAIL"),
        "critical_violations": sum(len(item["critical_violations"]) for item in results),
        "results": results,
    }
