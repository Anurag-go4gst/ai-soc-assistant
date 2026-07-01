"""Repair duplicate SOC review checklist sections before COE stop-condition gating."""

from __future__ import annotations

import re
from typing import Any

from app.chat.guidance_summary_renderer import is_guidance_summary_path
from app.evals.answer_efficacy_checks import analyst_card_text

_CHECKLIST_HEADER = re.compile(
    r"^SOC review checklist(?: before execution)?\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_CHECKLIST_MARKER = "soc review checklist"
_BULLET_ITEM = re.compile(r"^(?:\d+\.\s*|-\s*)(.+)$")


def collapse_duplicate_soc_review_checklist_text(text: str) -> str:
    """Collapse repeated SOC review checklist sections within one visible surface."""
    body = str(text or "").strip()
    if not body or body.lower().count(_CHECKLIST_MARKER) <= 1:
        return body

    lines = body.splitlines()
    prose: list[str] = []
    merged_items: list[str] = []
    section_items: list[str] = []
    in_section = False

    def flush_section() -> None:
        nonlocal section_items
        seen: set[str] = {existing.lower() for existing in merged_items}
        for item in section_items:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                merged_items.append(item)
        section_items = []

    for line in lines:
        stripped = line.strip()
        if _CHECKLIST_HEADER.match(stripped):
            if in_section:
                flush_section()
            in_section = True
            continue
        if in_section:
            if not stripped:
                continue
            match = _BULLET_ITEM.match(stripped)
            item = (match.group(1) if match else stripped).strip()
            if item and not item.endswith(":"):
                section_items.append(item)
            continue
        prose.append(line)

    if in_section:
        flush_section()

    result = "\n".join(prose).strip()
    if merged_items:
        block = "SOC review checklist:\n" + "\n".join(f"- {item}" for item in merged_items[:12])
        result = f"{result}\n\n{block}".strip() if result else block
    return result


def _surface_marker_count(analyst_response: Any | None, message: str) -> int:
    card_lower = analyst_card_text({"analyst_response": analyst_response.model_dump() if analyst_response else {}}).lower()
    message_lower = str(message or "").lower()
    return max(card_lower.count(_CHECKLIST_MARKER), message_lower.count(_CHECKLIST_MARKER))


def _strip_inline_checklist_from_summary(analyst_response: Any) -> Any:
    if str(getattr(analyst_response, "response_profile", "") or "") != "spl_only":
        return analyst_response
    owns_structured_checklist = bool(
        getattr(analyst_response, "analyst_checklist", None)
        or getattr(analyst_response, "recommended_actions", None)
        or getattr(analyst_response, "investigation_steps", None)
    )
    summary = str(getattr(analyst_response, "direct_answer_summary", "") or "").strip()
    if not owns_structured_checklist or _CHECKLIST_MARKER not in summary.lower():
        return analyst_response
    first_line = next((line.strip() for line in summary.splitlines() if line.strip()), "")
    if not first_line or first_line.lower().startswith(_CHECKLIST_MARKER):
        return analyst_response
    return analyst_response.model_copy(update={"direct_answer_summary": first_line[:500]})


def repair_duplicate_soc_review_checklist(
    analyst_response: Any | None,
    message: str,
    *,
    path_type: str | None = None,
) -> tuple[Any | None, str]:
    """Normalize duplicate checklist markers on the card and message surfaces."""
    if analyst_response is None and not str(message or "").strip():
        return analyst_response, message

    if analyst_response is not None and not is_guidance_summary_path(path_type):
        analyst_response = _strip_inline_checklist_from_summary(analyst_response)

    if _surface_marker_count(analyst_response, message) <= 1:
        return analyst_response, message

    repaired_message = collapse_duplicate_soc_review_checklist_text(str(message or ""))
    if analyst_response is None:
        return analyst_response, repaired_message

    updates: dict[str, Any] = {}
    for field in ("direct_answer_summary", "one_sentence_finding", "review_notice", "evidence_summary"):
        value = getattr(analyst_response, field, None)
        if isinstance(value, str) and value.strip():
            collapsed = collapse_duplicate_soc_review_checklist_text(value)
            if collapsed != value:
                updates[field] = collapsed

    owns_structured_checklist = bool(
        getattr(analyst_response, "analyst_checklist", None)
        or getattr(analyst_response, "recommended_actions", None)
        or getattr(analyst_response, "investigation_steps", None)
    )
    summary = str(
        updates.get("direct_answer_summary")
        or getattr(analyst_response, "direct_answer_summary", "")
        or ""
    ).strip()
    if owns_structured_checklist and summary and _CHECKLIST_MARKER in summary.lower():
        first_line = next((line.strip() for line in summary.splitlines() if line.strip()), "")
        if first_line and not first_line.lower().startswith(_CHECKLIST_MARKER):
            updates["direct_answer_summary"] = first_line[:500]

    if updates:
        analyst_response = analyst_response.model_copy(update=updates)
        analyst_response = _strip_inline_checklist_from_summary(analyst_response)

    if _surface_marker_count(analyst_response, repaired_message) > 1:
        repaired_message = collapse_duplicate_soc_review_checklist_text(repaired_message)

    return analyst_response, repaired_message
