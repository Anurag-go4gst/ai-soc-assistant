"""Context-local chat progress reporter for pipeline nodes."""

from __future__ import annotations

from contextvars import ContextVar

from app.chat.progress_events import (
    MCP_PENDING_USER_MESSAGE,
    ChatProgressStage,
    ProgressReporter,
)

_progress_var: ContextVar[ProgressReporter | None] = ContextVar("chat_progress_reporter", default=None)


def progress_reporter() -> ProgressReporter | None:
    return _progress_var.get()


def bind_progress_reporter(reporter: ProgressReporter | None):
    return _progress_var.set(reporter)


def reset_progress_reporter(token) -> None:
    _progress_var.reset(token)


def emit_stage(stage: ChatProgressStage, *, label: str | None = None, detail: str | None = None) -> None:
    reporter = progress_reporter()
    if reporter is not None:
        reporter.stage(stage, label=label, detail=detail)


def emit_heartbeat(stage: ChatProgressStage, label: str) -> None:
    reporter = progress_reporter()
    if reporter is not None:
        reporter.heartbeat(stage, label)


def emit_llm_degraded(*, code: str, message: str, recoverable: bool = True) -> None:
    reporter = progress_reporter()
    if reporter is not None:
        reporter.llm_degraded(code=code, message=message, recoverable=recoverable)


def emit_mcp_status_from_execution(execution: dict | None) -> None:
    """Surface MCP-unavailable messaging during checking_mcp without changing execution logic."""
    if execution is None:
        return
    status = str(execution.get("status") or "")
    block = execution.get("block_reason")
    tool_status = str(execution.get("tool_selection_status") or "")
    needs_pending_message = status in {
        "skipped",
        "requires_human_review",
        "blocked",
        "not_implemented",
        "unavailable",
    } or tool_status in {"blocked", "unavailable", "blocked_by_evidence_plan", "blocked_by_policy"}
    if block or needs_pending_message:
        reporter = progress_reporter()
        if reporter is not None:
            reporter.mcp_pending()
