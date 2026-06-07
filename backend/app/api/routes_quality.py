from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.auth.session import require_auth
from app.config import settings
from app.quality.promote_golden import promote_turn_to_golden
from app.quality.store import export_chat_turns_csv, get_chat_turn, list_chat_turns, record_feedback, record_review
from app.quality.summary import build_quality_summary

router = APIRouter(dependencies=[Depends(require_auth)])


class ChatFeedbackRequest(BaseModel):
    turn_id: str
    rating: str = Field(pattern="^(up|down|neutral)$")
    remark: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=120)


class QualityReviewRequest(BaseModel):
    root_cause: str
    review_notes: str = ""
    recommended_action: str = ""
    linked_issue: str | None = None
    linked_pr: str | None = None
    golden_case_id: str | None = None
    status: str = Field(default="open", pattern="^(open|fixed|wont_fix)$")


class PromoteGoldenRequest(BaseModel):
    case_id: str | None = Field(default=None, max_length=200)


@router.post("/chat/feedback")
def submit_chat_feedback(payload: ChatFeedbackRequest, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    try:
        feedback = record_feedback(
            turn_id=payload.turn_id,
            rating=payload.rating,
            remark=payload.remark,
            category=payload.category,
            user=user,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="turn_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"feedback": feedback, "saved": True}


@router.get("/quality/summary")
def quality_summary(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    _require_quality_review_access(user)
    return build_quality_summary()


@router.get("/quality/chat-turns")
def quality_chat_turns(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    _require_quality_review_access(user)
    rows = list_chat_turns(status=status_filter, limit=limit)
    return {"turns": rows, "count": len(rows)}


@router.get("/quality/flagged-turns")
def quality_flagged_turns(
    limit: int = Query(default=50, ge=1, le=500),
    user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Alias for the review queue filtered to flagged turns (frontend compatibility)."""
    _require_quality_review_access(user)
    rows = list_chat_turns(status="flagged", limit=limit)
    for row in rows:
        feedback = row.get("feedback") or []
        row["latest_feedback"] = feedback[-1] if feedback else None
    return {"turns": rows, "count": len(rows)}


@router.get("/quality/chat-turns/export")
def quality_chat_turns_export(
    export_format: str = Query(default="csv", alias="format", pattern="^csv$"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=500, ge=1, le=2000),
    user: dict[str, Any] = Depends(require_auth),
) -> PlainTextResponse:
    _require_quality_review_access(user)
    if export_format != "csv":
        raise HTTPException(status_code=400, detail="unsupported_format")
    body = export_chat_turns_csv(status=status_filter, limit=limit)
    return PlainTextResponse(content=body, media_type="text/csv")


@router.get("/quality/chat-turns/{turn_id}")
def quality_chat_turn_detail(turn_id: str, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    _require_quality_review_access(user)
    row = get_chat_turn(turn_id)
    if row is None:
        raise HTTPException(status_code=404, detail="turn_not_found")
    return {"turn": row}


@router.patch("/quality/chat-turns/{turn_id}/review")
def update_quality_review(
    turn_id: str,
    payload: QualityReviewRequest,
    user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    _require_quality_review_access(user)
    try:
        review = record_review(
            turn_id=turn_id,
            reviewer_id=str(user.get("username") or "reviewer"),
            root_cause=payload.root_cause,
            review_notes=payload.review_notes,
            recommended_action=payload.recommended_action,
            linked_issue=payload.linked_issue,
            linked_pr=payload.linked_pr,
            golden_case_id=payload.golden_case_id,
            status=payload.status,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="turn_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"review": review, "saved": True}


@router.post("/quality/chat-turns/{turn_id}/promote-golden")
def promote_golden_case(
    turn_id: str,
    payload: PromoteGoldenRequest | None = None,
    user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    _require_quality_review_access(user)
    try:
        return promote_turn_to_golden(turn_id, case_id=(payload.case_id if payload else None))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="turn_not_found") from exc


def _require_quality_review_access(user: dict[str, Any]) -> None:
    if not settings.quality_review_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quality_review_disabled")
    allowlist = {item.strip() for item in settings.quality_review_user_allowlist.split(",") if item.strip()}
    username = str(user.get("username") or "")
    role = str(user.get("role") or "")
    if role in {"quality_reviewer", "admin"} or username in allowlist:
        return
    if not allowlist and settings.quality_review_allow_any_authenticated:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="quality_review_forbidden")
