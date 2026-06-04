"""Durable best-effort chat turn ledger with in-process fallback.

The quality ledger must never break chat. Writes are attempted against the
configured Postgres database when available, while an in-process copy supports
local review and tests even if the DB is unavailable.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import asyncpg

from app.config import settings
from app.connectors.telemetry import metrics
from app.connectors.telemetry.redaction import MAX_SERIALIZED_PAYLOAD_BYTES, minimize, truncate
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

_MIGRATION_PATH = Path(__file__).resolve().parents[1] / "db" / "migrations" / "0002_answer_quality.sql"
_REMARK_MAX_LEN = 2000
_store_lock = Lock()
_turns: dict[str, dict[str, Any]] = {}
_feedback: dict[tuple[str, str], dict[str, Any]] = {}
_reviews: dict[str, dict[str, Any]] = {}
_schema_ready = False
_db_disabled_after_failure = False

_ROOT_CAUSES = {
    "routing_wrong",
    "use_case_missing",
    "catalog_mapping_wrong",
    "mitre_decision_wrong",
    "rag_missing_or_wrong",
    "spl_template_missing",
    "spl_template_wrong",
    "llm_fallback_wrong",
    "answer_wording_wrong",
    "frontend_display_wrong",
    "insufficient_user_context",
    "source_unavailable",
    "expected_behavior_user_education",
}


def post_chat_response(
    response: PlaceholderResponse,
    request: ChatRequest,
    *,
    entrypoint: str,
    user: dict[str, Any] | str | None = None,
) -> PlaceholderResponse:
    """Attach a turn id and record answer-quality context.

    Demo/fixture answers are intentionally excluded from the live quality
    ledger so analyst quality metrics are not polluted by synthetic scenarios.
    """
    if _is_demo_or_fixture(response):
        return response
    turn_id = response.turn_id or str(uuid4())
    updated = response.model_copy(update={"turn_id": turn_id})
    try:
        record_chat_turn(updated, request, entrypoint=entrypoint, user=user)
    except Exception:  # noqa: BLE001 - quality ledger must never break chat
        metrics.increment("quality_ledger_write_failures")
    return updated


def record_chat_turn(
    response: PlaceholderResponse,
    request: ChatRequest,
    *,
    entrypoint: str,
    user: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    turn_id = response.turn_id or str(uuid4())
    payload = response.model_dump(mode="json")
    user_id = _user_id(user)
    selected_use_case = payload.get("selected_use_case") or {}
    evidence_plan = payload.get("evidence_plan") or {}
    execution = payload.get("execution") or {}
    source_evidence = payload.get("source_evidence") or []
    record = {
        "turn_id": turn_id,
        "trace_id": response.trace_id,
        "created_at": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "session_id": None,
        "entrypoint": entrypoint,
        "user_query": request.message,
        "normalized_query": _normalize_query(request.message),
        "selected_skill": payload.get("selected_skill"),
        "selected_use_case_id": selected_use_case.get("use_case_id") if isinstance(selected_use_case, dict) else None,
        "question_ref": _question_ref(payload),
        "answer_mode": evidence_plan.get("answer_mode") if isinstance(evidence_plan, dict) else None,
        "response_mode": payload.get("response_mode"),
        "final_message": payload.get("message"),
        "analyst_summary": payload.get("analyst_summary"),
        "analyst_response": _bounded_json(payload.get("analyst_response")),
        "candidate_spl": _candidate_spl(payload),
        "spl_validation": _bounded_json(payload.get("spl_validation")),
        "mitre_decision": _bounded_json(payload.get("mitre_decision")),
        "mitre_mappings": _bounded_json(payload.get("mitre_mappings")),
        "source_evidence_refs": _source_refs(source_evidence),
        "control_plane_trace": _bounded_json(payload.get("control_plane_trace")),
        "execution_status": execution.get("status") if isinstance(execution, dict) else None,
        "llm_used": _llm_used(payload),
        "rag_used": bool(source_evidence),
        "mcp_used": bool(execution and execution.get("selected_mcp_tool")) if isinstance(execution, dict) else False,
        "quality_status": "unreviewed",
        "golden_candidate": False,
    }
    with _store_lock:
        _turns[turn_id] = record
    _try_persist_turn(record)
    return record


def record_feedback(
    *,
    turn_id: str,
    rating: str,
    remark: str | None = None,
    category: str | None = None,
    user: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    if rating not in {"up", "down", "neutral"}:
        raise ValueError("invalid_feedback_rating")
    if turn_id not in _turns:
        raise KeyError("turn_not_found")
    user_id = _user_id(user) or "anonymous"
    now = datetime.now(UTC).isoformat()
    key = (turn_id, user_id)
    prior = _feedback.get(key)
    record = {
        "feedback_id": prior.get("feedback_id") if prior else str(uuid4()),
        "turn_id": turn_id,
        "trace_id": _turns[turn_id].get("trace_id"),
        "created_at": prior.get("created_at") if prior else now,
        "updated_at": now,
        "user_id": user_id,
        "rating": rating,
        "remark": truncate(remark, _REMARK_MAX_LEN),
        "category": truncate(category, 120),
        "review_status": "new",
        "history": [*list((prior or {}).get("history") or []), _feedback_history_item(prior, rating, remark)],
    }
    with _store_lock:
        _feedback[key] = record
        turn = _turns[turn_id]
        turn["quality_status"] = "flagged" if rating == "down" else "accepted" if rating == "up" else "unreviewed"
        if rating == "down":
            turn["golden_candidate"] = True
    _try_persist_feedback(record)
    return record


def record_review(
    *,
    turn_id: str,
    reviewer_id: str,
    root_cause: str,
    review_notes: str = "",
    recommended_action: str = "",
    status: str = "open",
    linked_issue: str | None = None,
    linked_pr: str | None = None,
    golden_case_id: str | None = None,
) -> dict[str, Any]:
    if turn_id not in _turns:
        raise KeyError("turn_not_found")
    if root_cause not in _ROOT_CAUSES:
        raise ValueError("invalid_root_cause")
    if status not in {"open", "fixed", "wont_fix"}:
        raise ValueError("invalid_review_status")
    record = {
        "review_id": str(uuid4()),
        "turn_id": turn_id,
        "created_at": datetime.now(UTC).isoformat(),
        "reviewer_id": reviewer_id,
        "root_cause": root_cause,
        "review_notes": truncate(review_notes),
        "recommended_action": truncate(recommended_action),
        "linked_issue": truncate(linked_issue, 500),
        "linked_pr": truncate(linked_pr, 500),
        "golden_case_id": truncate(golden_case_id, 200),
        "status": status,
    }
    with _store_lock:
        _reviews[record["review_id"]] = record
        _turns[turn_id]["quality_status"] = "in_review" if status == "open" else status
        if golden_case_id:
            _turns[turn_id]["golden_candidate"] = True
    _try_persist_review(record)
    return record


def list_chat_turns(
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with _store_lock:
        rows = list(_turns.values())
    if status:
        rows = [row for row in rows if row.get("quality_status") == status]
    return list(reversed(rows[-limit:]))


def get_chat_turn(turn_id: str) -> dict[str, Any] | None:
    with _store_lock:
        turn = _turns.get(turn_id)
        if not turn:
            return None
        feedback = [item for item in _feedback.values() if item.get("turn_id") == turn_id]
        reviews = [item for item in _reviews.values() if item.get("turn_id") == turn_id]
    return {**turn, "feedback": feedback, "reviews": reviews}


def clear_quality_store_for_tests() -> None:
    global _db_disabled_after_failure, _schema_ready
    with _store_lock:
        _turns.clear()
        _feedback.clear()
        _reviews.clear()
    _db_disabled_after_failure = False
    _schema_ready = False


def _is_demo_or_fixture(response: PlaceholderResponse) -> bool:
    if response.demo_mode:
        return True
    governance = response.experience_center_governance
    if governance is not None:
        return True
    payload = response.model_dump(mode="json")
    return bool((payload.get("spl_template") or {}).get("coe_synthetic_fixture"))


def _user_id(user: dict[str, Any] | str | None) -> str | None:
    if isinstance(user, str):
        return user
    if isinstance(user, dict):
        return str(user.get("username") or user.get("user_id") or "") or None
    return None


def _normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def _question_ref(payload: dict[str, Any]) -> str | None:
    shadow = payload.get("route_plan_shadow") or {}
    if isinstance(shadow, dict):
        runtime_map = shadow.get("question_runtime_map") or {}
        if isinstance(runtime_map, dict) and runtime_map.get("question_ref"):
            return str(runtime_map["question_ref"])
    return None


def _candidate_spl(payload: dict[str, Any]) -> str | None:
    validation = payload.get("spl_validation") or {}
    if isinstance(validation, dict) and validation.get("normalized_spl"):
        return str(validation["normalized_spl"])
    candidate = payload.get("candidate_spl") or {}
    if isinstance(candidate, dict) and candidate.get("candidate_spl"):
        return str(candidate["candidate_spl"])
    return None


def _source_refs(source_evidence: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if not isinstance(source_evidence, list):
        return refs
    for item in source_evidence[:25]:
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "evidence_id": item.get("evidence_id"),
                "source_type": item.get("source_type"),
                "source_name": item.get("source_name"),
                "collection_status": item.get("collection_status"),
                "result_count": item.get("result_count"),
                "fields_returned": item.get("fields_returned"),
                "warnings": item.get("warnings"),
            }
        )
    return refs


def _llm_used(payload: dict[str, Any]) -> bool:
    for key in ("candidate_spl", "spl_validation", "synthesis_status"):
        value = payload.get(key)
        if isinstance(value, dict) and any(value.get(flag) for flag in ("llm_supported", "llm_fallback_used", "llm_called")):
            return True
    return False


def _bounded_json(value: Any) -> Any:
    minimized = minimize(value)
    serialized = json.dumps(minimized, default=str, sort_keys=True)
    if len(serialized.encode("utf-8")) > MAX_SERIALIZED_PAYLOAD_BYTES:
        return {"__truncated__": True, "preview": serialized[:1000]}
    return minimized


def _feedback_history_item(prior: dict[str, Any] | None, rating: str, remark: str | None) -> dict[str, Any]:
    return {
        "at": datetime.now(UTC).isoformat(),
        "previous_rating": prior.get("rating") if prior else None,
        "rating": rating,
        "remark": truncate(remark, _REMARK_MAX_LEN),
    }


def _try_persist_turn(record: dict[str, Any]) -> None:
    _run_db(
        """
        INSERT INTO chat_turns (
            turn_id, trace_id, user_id, session_id, entrypoint, user_query, normalized_query,
            selected_skill, selected_use_case_id, question_ref, answer_mode, response_mode,
            final_message, analyst_summary, analyst_response, candidate_spl, spl_validation,
            mitre_decision, mitre_mappings, source_evidence_refs, control_plane_trace,
            execution_status, llm_used, rag_used, mcp_used, quality_status, golden_candidate
        )
        VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb,$16,$17::jsonb,
            $18::jsonb,$19::jsonb,$20::jsonb,$21::jsonb,$22,$23,$24,$25,$26,$27
        )
        ON CONFLICT (turn_id) DO NOTHING
        """,
        record["turn_id"],
        record["trace_id"],
        record["user_id"],
        record["session_id"],
        record["entrypoint"],
        record["user_query"],
        record["normalized_query"],
        record["selected_skill"],
        record["selected_use_case_id"],
        record["question_ref"],
        record["answer_mode"],
        record["response_mode"],
        record["final_message"],
        record["analyst_summary"],
        _json(record["analyst_response"]),
        record["candidate_spl"],
        _json(record["spl_validation"]),
        _json(record["mitre_decision"]),
        _json(record["mitre_mappings"]),
        _json(record["source_evidence_refs"]),
        _json(record["control_plane_trace"]),
        record["execution_status"],
        record["llm_used"],
        record["rag_used"],
        record["mcp_used"],
        record["quality_status"],
        record["golden_candidate"],
    )


def _try_persist_feedback(record: dict[str, Any]) -> None:
    _run_db(
        """
        INSERT INTO chat_answer_feedback (
            feedback_id, turn_id, trace_id, user_id, rating, remark, category, review_status, history
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)
        ON CONFLICT (turn_id, user_id) DO UPDATE SET
            rating = EXCLUDED.rating,
            remark = EXCLUDED.remark,
            category = EXCLUDED.category,
            review_status = EXCLUDED.review_status,
            history = EXCLUDED.history,
            updated_at = now()
        """,
        record["feedback_id"],
        record["turn_id"],
        record["trace_id"],
        record["user_id"],
        record["rating"],
        record["remark"],
        record["category"],
        record["review_status"],
        _json(record["history"]),
    )


def _try_persist_review(record: dict[str, Any]) -> None:
    _run_db(
        """
        INSERT INTO answer_quality_reviews (
            review_id, turn_id, reviewer_id, root_cause, review_notes, recommended_action,
            linked_issue, linked_pr, golden_case_id, status
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        record["review_id"],
        record["turn_id"],
        record["reviewer_id"],
        record["root_cause"],
        record["review_notes"],
        record["recommended_action"],
        record["linked_issue"],
        record["linked_pr"],
        record["golden_case_id"],
        record["status"],
    )


def _run_db(sql: str, *args: Any) -> None:
    global _db_disabled_after_failure, _schema_ready
    if _db_disabled_after_failure or "change-me@postgres" in settings.database_url:
        return

    async def _inner() -> None:
        global _schema_ready
        conn = await asyncpg.connect(settings.database_url, timeout=1.0)
        try:
            if not _schema_ready:
                await conn.execute(_MIGRATION_PATH.read_text(encoding="utf-8"))
                _schema_ready = True
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    try:
        asyncio.run(_inner())
    except Exception:
        _db_disabled_after_failure = True
        metrics.increment("telemetry_write_failures")


def _json(value: Any) -> str:
    return json.dumps(minimize(value), separators=(",", ":"), sort_keys=True, default=str)
