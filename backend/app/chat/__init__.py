"""Live /chat orchestration package."""

from __future__ import annotations

from typing import Any

__all__ = ["build_live_chat_response"]


def __getattr__(name: str) -> Any:
    if name == "build_live_chat_response":
        from app.chat.pipeline import build_live_chat_response

        return build_live_chat_response
    raise AttributeError(name)
