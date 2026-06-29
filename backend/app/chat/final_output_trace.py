"""Final analyst-visible output projection for the debug trace bundle.

The debug bundle exposes routing/SPL/MCP explainability but not the answer the
analyst actually saw. ``build_final_output_trace`` produces a bounded, read-only
snapshot of the published response so a trace reads "what was asked → what came
back" without re-running the turn. It never asserts authority and never carries
raw evidence rows — only the already-published answer text plus deterministic
fact labels (severity, MITRE status, HIL, guard).
"""

from __future__ import annotations

from typing import Any


def _bounded(text: Any, *, limit: int = 600) -> str | None:
    """Collapse whitespace and bound length; None for non-strings/empties."""
    if not isinstance(text, str):
        return None
    collapsed = " ".join(text.split()).strip()
    if not collapsed:
        return None
    if len(collapsed) > limit:
        collapsed = collapsed[: limit - 1].rstrip() + "…"
    return collapsed


def _dig(payload: dict[str, Any], *keys: str) -> Any:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def build_final_output_trace(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Redacted snapshot of the final analyst-visible output.

    ``payload`` is a serialized response (``response.model_dump(mode="json")``).
    All fields are optional and tolerant of missing keys; the function never
    raises so telemetry linkage cannot break chat.
    """
    if not isinstance(payload, dict):
        return {}

    severity = (
        _dig(payload, "severity_decision", "severity_label")
        or _dig(payload, "run_contract", "severity_label")
    )
    guard_status = (
        payload.get("answer_guard_status")
        or _dig(payload, "answer_guard", "guard_status")
    )
    human_review = payload.get("human_review")
    hil_required = bool(human_review) or bool(_dig(payload, "run_contract", "effective_hil_required"))
    mitre_status = _dig(payload, "mitre_decision", "status") or _dig(
        payload, "mitre_decision", "evidence_status"
    )

    return {
        "message": _bounded(payload.get("message")),
        "analyst_summary": _bounded(payload.get("analyst_summary")),
        "selected_skill": payload.get("selected_skill"),
        "answer_mode": payload.get("answer_mode")
        or _dig(payload, "evidence_plan", "answer_mode"),
        "severity_label": severity,
        "mitre_status": mitre_status,
        "hil_required": hil_required,
        "hil_reason": _dig(payload, "human_review", "reason") if isinstance(human_review, dict) else None,
        "guard_status": guard_status,
        "final_answer_safety_status": payload.get("final_answer_safety_status"),
        "execution_status": _dig(payload, "execution", "status"),
    }


def final_output_answer_preview(payload: dict[str, Any] | None, *, limit: int = 200) -> str | None:
    """Prefer the real analyst-visible answer for the trace-list preview.

    The RunContract ``build_answer_preview`` often yields a canned template
    string; the analyst saw ``message`` / ``analyst_summary``. Prefer those.
    """
    if not isinstance(payload, dict):
        return None
    for key in ("message", "analyst_summary"):
        preview = _bounded(payload.get(key), limit=limit)
        if preview:
            return preview
    return None
