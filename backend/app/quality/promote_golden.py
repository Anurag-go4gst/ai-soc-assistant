"""Promote a flagged chat turn into a draft golden-answer regression case."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.quality.store import get_chat_turn, mark_golden_candidate

REPO_ROOT = Path(__file__).resolve().parents[3]
DRAFT_DIR = REPO_ROOT / "backend/app/evals/golden_answers"
FLAGGED_FILE = DRAFT_DIR / "flagged_regressions.jsonl"


def _category_for_turn(turn: dict[str, Any]) -> str:
    answer_mode = (turn.get("answer_mode") or "").lower()
    if answer_mode in {"rag_only", "rag_policy"}:
        return "rag_policy"
    if answer_mode == "clarification" or turn.get("quality_status") == "flagged":
        response_mode = (turn.get("response_mode") or "").lower()
        if "clarification" in response_mode:
            return "clarification"
    if turn.get("mitre_mappings"):
        return "mitre_mapping"
    if turn.get("candidate_spl"):
        return "spl_candidate"
    return "answer"


def build_draft_golden_case(turn: dict[str, Any], *, case_id: str | None = None) -> dict[str, Any]:
    """Build a draft JSONL row from a stored turn (observed + empty expected for review)."""
    draft_id = case_id or f"flagged.{turn.get('turn_id') or uuid4()}"
    mitre_decision = turn.get("mitre_decision") if isinstance(turn.get("mitre_decision"), dict) else {}
    techniques = []
    if isinstance(mitre_decision.get("techniques"), list):
        for item in mitre_decision["techniques"]:
            if isinstance(item, dict) and item.get("technique_id"):
                techniques.append(str(item["technique_id"]))
            elif isinstance(item, str):
                techniques.append(item)
    observed_expected = {
        "selected_skill": turn.get("selected_skill"),
        "selected_use_case_id": turn.get("selected_use_case_id"),
        "answer_mode": turn.get("answer_mode"),
        "response_mode": turn.get("response_mode"),
    }
    if turn.get("candidate_spl"):
        observed_expected["candidate_spl"] = {"required": True, "approved": bool((turn.get("spl_validation") or {}).get("approved"))}
    if techniques:
        observed_expected["mitre"] = {"visible": techniques}
    return {
        "case_id": draft_id,
        "tier": 3,
        "source": "flagged_regression",
        "query": turn.get("user_query") or "",
        "category": _category_for_turn(turn),
        "tags": ["promoted_from_ledger", "needs_review"],
        "source_refs": [f"chat_turn:{turn.get('turn_id')}"],
        "notes": "Draft generated from live chat turn; reviewer should tighten expected assertions.",
        "observed_snapshot": {
            "final_message": turn.get("final_message"),
            "execution_status": turn.get("execution_status"),
            "mitre_decision": turn.get("mitre_decision"),
            "spl_validation": turn.get("spl_validation"),
        },
        "expected": observed_expected,
    }


def append_draft_case(case: dict[str, Any]) -> Path:
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    with FLAGGED_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(case, sort_keys=True) + "\n")
    return FLAGGED_FILE


def promote_turn_to_golden(turn_id: str, *, case_id: str | None = None) -> dict[str, Any]:
    turn = get_chat_turn(turn_id)
    if turn is None:
        raise KeyError("turn_not_found")
    case = build_draft_golden_case(turn, case_id=case_id)
    case["promoted_at"] = datetime.now(UTC).isoformat()
    path = append_draft_case(case)
    mark_golden_candidate(turn_id, golden_case_id=case["case_id"])
    return {"golden_case": case, "draft_path": str(path), "golden_case_id": case["case_id"]}
