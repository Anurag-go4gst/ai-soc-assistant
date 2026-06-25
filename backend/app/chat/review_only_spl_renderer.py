"""Dedicated renderer for review-only SPL draft answers.

When the RunContract says the canonical skill is ``spl_generation`` with a renderable
candidate that was not executed, the visible answer is composed by one renderer that
owns section ordering and labels. This replaces the generic multi-producer composition
(title / review-type banner / investigation-plan / analyst-workflow) which otherwise
prepends competing headings ahead of the review-only SPL answer shape.

This is section-level ownership, not string scrubbing: the renderer emits exactly the
sections it wants, in a fixed order, and the caller suppresses the competing card
producers so they cannot re-introduce duplicate/competing sections.

Governance is unchanged here — severity, execution status, HIL, MCP posture, source
evidence, and SPL validation are all read from the already-decided RunContract /
analyst response. The renderer only shapes the visible text.
"""

from __future__ import annotations

import re
from typing import Any

_MAIN_TITLE = "Review-only SPL draft — no live query was executed"
_SEVERITY_NOT_ASSIGNED = "Not assigned from this question alone"
_EXECUTION_LINE = "Execution: Not executed"
_REVIEW_LINE = "Review: HIL/SOC review required before any future execution path"
_REVIEW_ONLY_NOTICE = (
    "This is a lab-only draft SPL preview. It is not governed, not approved, and not executed."
)
_CHECKLIST_HEADER = "SOC review checklist before execution:"
_HOW_PRODUCED = "How this answer was produced: review-only / no live execution"

_PRIORITY_PREFIX = re.compile(r"^P[1-4]\s*[—\-–:]\s*", re.IGNORECASE)

# Generic fallback checklist for review-only SPL drafts without a family-specific one.
_GENERIC_CHECKLIST: tuple[str, ...] = (
    "Confirm the index, sourcetype, and field placeholders against your source profile.",
    "Identify the source and destination assets relevant to the question.",
    "Review the draft SPL filters, time window, and result limit before any execution.",
    "Compare any matches with approved change or maintenance activity.",
    "Escalate only after required evidence is collected and documented.",
    "Do not declare compromise from this draft alone.",
)

_FIREWALL_SCOPE = (
    "Scope: IT-to-OT firewall boundary review for external or remote-access-style "
    "connections to substation/OT networks."
)


def is_review_only_spl_answer(run_contract: Any) -> bool:
    """True when the answer is a renderable, non-executed SPL-generation draft.

    Mirrors the agreed trigger:
        run_contract.routing.canonical_skill == "spl_generation"
        and run_contract.spl_candidate_renderable is True
        and run_contract.execution_status != "executed"
    """
    if run_contract is None:
        return False
    routing = getattr(run_contract, "routing", None)
    canonical_skill = getattr(routing, "canonical_skill", None)
    return (
        canonical_skill == "spl_generation"
        and getattr(run_contract, "spl_candidate_renderable", False) is True
        and getattr(run_contract, "execution_status", "") != "executed"
    )


def _strip_priority_prefix(text: str) -> str:
    return _PRIORITY_PREFIX.sub("", str(text or "")).strip()


def _severity_text(analyst_response: Any) -> str:
    label = _strip_priority_prefix(str(getattr(analyst_response, "severity_label", "") or ""))
    if not label or "not assigned" in label.lower():
        return _SEVERITY_NOT_ASSIGNED
    return label


def _scope_line(analyst_response: Any) -> str:
    """Family-aware scope line; only assert the IT-to-OT framing on a strong match."""
    haystack = " ".join(
        str(getattr(analyst_response, field, "") or "")
        for field in ("finding_title", "scenario_label")
    ).lower()
    if ("it-to-ot" in haystack or "it to ot" in haystack) or (
        "firewall" in haystack and ("ot" in haystack or "boundary" in haystack)
    ):
        return _FIREWALL_SCOPE
    return (
        "Scope: Review-only SPL draft for the requested live-data query; validate the "
        "source profile before review. No governed template is bound and nothing was executed."
    )


def _checklist_items(analyst_response: Any, draft_preview: dict[str, Any] | None) -> list[str]:
    for source in (
        getattr(analyst_response, "analyst_checklist", None),
        (draft_preview or {}).get("investigation_checklist") if isinstance(draft_preview, dict) else None,
    ):
        items = [_strip_priority_prefix(str(item)) for item in (source or []) if str(item).strip()]
        if items:
            return items
    return list(_GENERIC_CHECKLIST)


def _draft_spl_text(analyst_response: Any, draft_preview: dict[str, Any] | None) -> str:
    if isinstance(draft_preview, dict):
        spl = str(draft_preview.get("draft_spl") or "").strip()
        if spl:
            return spl
    return str(getattr(analyst_response, "draft_spl_code", "") or "").strip()


def _assumptions(draft_preview: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft_preview, dict):
        return []
    return [str(item).strip() for item in (draft_preview.get("assumptions") or []) if str(item).strip()]


def render_review_only_spl_answer(
    *,
    analyst_response: Any,
    draft_preview: dict[str, Any] | None,
) -> str:
    """Compose the single clean visible answer for a review-only SPL draft.

    Fixed section order: title, status block, scope, review-only notice, SOC review
    checklist (numbered, once), draft SPL preview (once), assumptions (once), and an
    optional "How this answer was produced" line. The renderer never emits live-result
    language, severity priority prefixes, or a competing title/review-type banner.
    """
    lines: list[str] = [_MAIN_TITLE, ""]

    lines.append(f"Severity: {_severity_text(analyst_response)}")
    lines.append(_EXECUTION_LINE)
    lines.append(_REVIEW_LINE)
    lines.append(_scope_line(analyst_response))
    lines.append("")

    lines.append(_REVIEW_ONLY_NOTICE)
    lines.append("")

    lines.append(_CHECKLIST_HEADER)
    for index, item in enumerate(_checklist_items(analyst_response, draft_preview), start=1):
        lines.append(f"{index}. {item}")

    draft_spl = _draft_spl_text(analyst_response, draft_preview)
    if draft_spl:
        lines.append("")
        lines.append("Draft SPL preview:")
        lines.append(draft_spl)

    assumptions = _assumptions(draft_preview)
    if assumptions:
        lines.append("")
        lines.append("Assumptions and placeholders:")
        for item in assumptions:
            lines.append(f"- {item}")

    lines.append("")
    lines.append(_HOW_PRODUCED)

    return "\n".join(lines).strip()


def apply_review_only_spl_render(
    *,
    run_contract: Any,
    analyst_response: Any,
    message: str,
    draft_preview: dict[str, Any] | None,
) -> tuple[Any, str]:
    """For review-only SPL answers, own the visible answer and suppress competing producers.

    Returns ``(analyst_response, message)``. When the trigger does not match, inputs are
    returned unchanged. Governance fields are not touched — only presentation:
      * ``message`` becomes the single composed visible answer.
      * The card's competing title / review-type / investigation-plan / analyst-workflow
        producers are suppressed at the section level (not scrubbed afterwards):
          - ``finding_title`` becomes the review-only title.
          - ``response_profile`` becomes ``spl_only`` so the frontend drops the
            investigation-plan, MITRE, and model-reasoning phases.
          - ``investigation_steps`` and ``recommended_actions`` are cleared so the same
            checklist is not rendered twice under "Investigation steps / Analyst workflow".
          - ``scenario_label`` is cleared so it cannot prepend a competing heading.
          - ``direct_answer_summary`` carries only the status/scope/notice header.
    """
    if not is_review_only_spl_answer(run_contract) or analyst_response is None:
        return analyst_response, message

    # Scope to lab-only draft answers. A governed, validated SPL draft (no lab preview,
    # spl_code present) is also review-only/not-executed but keeps its "Governed SPL
    # draft ready" wording — it is not "not governed, not approved".
    has_lab_draft = (
        isinstance(draft_preview, dict) and str(draft_preview.get("draft_spl") or "").strip()
    ) or bool(str(getattr(analyst_response, "draft_spl_code", "") or "").strip())
    if not has_lab_draft:
        return analyst_response, message

    composed = render_review_only_spl_answer(
        analyst_response=analyst_response,
        draft_preview=draft_preview,
    )

    # Header text owned by the card summary (status block + scope only). The title is not
    # repeated here (the card renders ``finding_title`` as its heading), and the lab-only
    # notice is not repeated here either — it stays in the composed message and in the
    # card's owned ``spl_draft_preview.warning`` section, so the warning is not rendered
    # twice within the card surface. Checklist and SPL own their own sections.
    header_lines = [
        f"Severity: {_severity_text(analyst_response)}",
        _EXECUTION_LINE,
        _REVIEW_LINE,
        _scope_line(analyst_response),
    ]

    updates: dict[str, Any] = {
        "finding_title": _MAIN_TITLE,
        "scenario_label": None,
        "response_profile": "spl_only",
        "investigation_steps": [],
        "recommended_actions": [],
        # ``severity_rationale`` carries the generic "Review type: analytics/query
        # review." banner; the status block already states severity, so clear it (and the
        # safety note) for this path so no competing top-level line is rendered.
        "severity_rationale": None,
        "severity_safety_note": None,
        "direct_answer_summary": "\n".join(header_lines),
        "analyst_checklist": _checklist_items(analyst_response, draft_preview),
    }
    updated = analyst_response.model_copy(update=updates)
    return updated, composed
