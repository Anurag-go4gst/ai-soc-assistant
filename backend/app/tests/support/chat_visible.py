"""Shared helpers for asserting analyst-visible chat surfaces in tests."""

from __future__ import annotations

import re
from typing import Any

from app.evals.answer_efficacy_checks import analyst_visible_text

GOVERNED_SPL_READY_STUB = (
    "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
)

REVIEW_ONLY_SPL_TITLE = re.compile(
    r"^Review-only SPL draft — no live query was (?:executed|performed)\.?$",
    re.IGNORECASE,
)

REVIEW_ONLY_NOTICE = re.compile(
    r"Review only — not (?:executed|performed)",
    re.IGNORECASE,
)


def _analyst_dict(response: Any) -> dict[str, Any]:
    analyst = getattr(response, "analyst_response", None)
    if analyst is None:
        return {}
    if hasattr(analyst, "model_dump"):
        return analyst.model_dump()
    if isinstance(analyst, dict):
        return analyst
    return {}


def visible_chat_prose(response: Any) -> str:
    """Merge top-level message and analyst-card prose (card-owned section design)."""
    payload: dict[str, Any] = {
        "message": getattr(response, "message", None) or "",
        "analyst_summary": getattr(response, "analyst_summary", None) or "",
        "analyst_response": _analyst_dict(response),
    }
    parts = [analyst_visible_text(payload)]
    analyst = _analyst_dict(response)
    for field in ("finding_title", "draft_spl_code", "spl_code", "spl_status_detail"):
        value = analyst.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "\n".join(part for part in parts if part).strip()


def spl_visible_text(response: Any) -> str:
    """SPL text from any governed surface (message, card, candidate, draft preview)."""
    parts = [visible_chat_prose(response)]
    candidate = getattr(response, "candidate_spl", None)
    if candidate is not None:
        if hasattr(candidate, "model_dump"):
            candidate = candidate.model_dump()
        if isinstance(candidate, dict):
            parts.append(str(candidate.get("candidate_spl") or ""))
    draft = getattr(response, "spl_draft_preview", None)
    if draft is not None:
        if hasattr(draft, "model_dump"):
            draft = draft.model_dump()
        if isinstance(draft, dict):
            parts.append(str(draft.get("draft_spl") or ""))
    spl_validation = getattr(response, "spl_validation", None)
    if spl_validation is not None:
        if hasattr(spl_validation, "model_dump"):
            spl_validation = spl_validation.model_dump()
        if isinstance(spl_validation, dict):
            parts.append(str(spl_validation.get("normalized_spl") or ""))
    return "\n".join(parts)


def first_visible_line(response: Any) -> str:
    title = str(_analyst_dict(response).get("finding_title") or "").strip()
    if title:
        return title
    for line in visible_chat_prose(response).splitlines():
        if line.strip():
            return line.strip()
    return ""


def assert_governed_spl_review_posture(response: Any) -> None:
    """Governed SPL is present, review-only, and not executed."""
    assert getattr(response, "workflow_plan", None) is not None
    assert response.workflow_plan.execution_enabled is False
    spl_blob = spl_visible_text(response).lower()
    assert "index=" in spl_blob or "search " in spl_blob
    prose = visible_chat_prose(response).lower()
    analyst = _analyst_dict(response)
    review_markers = (
        "not executed",
        "not performed",
        "review",
        "hil",
        "spl:",
        "blocked",
    )
    assert any(marker in prose for marker in review_markers) or bool(
        analyst.get("spl_code") or analyst.get("draft_spl_code")
    )
    execution = getattr(response, "execution", None)
    if execution is not None:
        status = getattr(execution, "status", None) or (
            execution.get("status") if isinstance(execution, dict) else None
        )
        assert status != "executed"


def visible_from_payload(payload: dict[str, Any]) -> str:
    """Visible prose from a ``model_dump(mode='json')`` chat payload."""
    return visible_chat_prose(type("_R", (), payload)())


def spl_from_payload(payload: dict[str, Any]) -> str:
    parts = [visible_from_payload(payload)]
    candidate = payload.get("candidate_spl") or {}
    if isinstance(candidate, dict):
        parts.append(str(candidate.get("candidate_spl") or ""))
    draft = payload.get("spl_draft_preview") or {}
    if isinstance(draft, dict):
        parts.append(str(draft.get("draft_spl") or ""))
    analyst = payload.get("analyst_response") or {}
    if isinstance(analyst, dict):
        parts.append(str(analyst.get("draft_spl_code") or ""))
        parts.append(str(analyst.get("spl_code") or ""))
    return "\n".join(parts)


def assert_review_only_title(text: str) -> None:
    first = next((line for line in text.splitlines() if line.strip()), text.strip())
    assert REVIEW_ONLY_SPL_TITLE.match(first), first
