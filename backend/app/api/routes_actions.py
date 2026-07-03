"""Item 6.1 — action lane approval endpoints.

Every action proposed by the pipeline sits in `pending_approval` until an
authenticated analyst approves or denies it here. Unauthenticated requests
are rejected 401 by `require_auth` before any handler code runs — nothing is
ever auto-executed.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.actions.action_lane import approve_action, deny_action, get_action_lane_store
from app.auth.session import require_auth

router = APIRouter()


def _username(user: dict[str, Any]) -> str:
    return str(user.get("username") or user.get("user_id") or "unknown_analyst")


@router.get("/actions/{action_id}", dependencies=[Depends(require_auth)])
def get_action(action_id: str) -> dict[str, Any]:
    proposal = get_action_lane_store().get(action_id)
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="action_not_found")
    return proposal.model_dump()


@router.post("/actions/{action_id}/approve")
def approve(action_id: str, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    proposal = approve_action(action_id, approver=_username(user))
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="action_not_found")
    return proposal.model_dump()


@router.post("/actions/{action_id}/deny")
def deny(action_id: str, user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    proposal = deny_action(action_id, approver=_username(user))
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="action_not_found")
    return proposal.model_dump()
