"""Render rich deterministic guidance into direct_answer_summary for guided/guidance rows."""

from __future__ import annotations

import re
from typing import Any

from app.chat.guidance_templates import build_investigation_triage_guidance
from app.schemas.responses import AnalystResponseEnvelope

GUIDANCE_SUMMARY_PATH_TYPES = frozenset(
    {
        "guided_investigation",
        "hybrid_investigation",
        "generic_soc_guidance",
        "spl_review_plus_rag",
        "mitre_context_required",
    }
)

_THIN_GUIDANCE_STUB = re.compile(
    r"\b("
    r"guided investigation prepared|"
    r"generic soc guidance path selected|"
    r"routing complete\.?\s*spl is not required|"
    r"review-only answer prepared"
    r")\b",
    re.IGNORECASE,
)
_CHECKLIST_MARKER = "soc review checklist"


def is_guidance_summary_path(path_type: str | None) -> bool:
    return str(path_type or "") in GUIDANCE_SUMMARY_PATH_TYPES


def apply_guidance_summary_render(
    analyst_response: AnalystResponseEnvelope | None,
    message: str,
    *,
    path_type: str | None,
    evidence_plan: dict[str, Any] | None,
    answer_contract: Any | None,
    user_query: str,
    llm_composer_used: bool = False,
) -> tuple[AnalystResponseEnvelope | None, str]:
    """Pull evidence-plan checklist/workflow into the card summary for guidance paths."""
    if not is_guidance_summary_path(path_type) or analyst_response is None:
        return analyst_response, message
    if str(getattr(analyst_response, "response_profile", "") or "") == "spl_only":
        return analyst_response, message

    summary = str(analyst_response.direct_answer_summary or message or "").strip()
    thin_stub = _is_thin_guidance_stub(summary)
    if llm_composer_used and summary:
        return analyst_response, message or summary
    items = _collect_guidance_items(
        analyst_response=analyst_response,
        evidence_plan=evidence_plan,
        answer_contract=answer_contract,
    )
    has_checklist = _CHECKLIST_MARKER in summary.lower()
    if not items and not thin_stub:
        return analyst_response, message
    if has_checklist and not thin_stub and len(summary.split()) >= 120:
        return analyst_response, message

    lead = _lead_prose(summary, user_query=user_query, path_type=path_type)
    # Checklist items belong in investigation_steps / recommended_actions /
    # analyst_checklist only. final_answer_validator Gate 3A rejects checklist
    # text embedded in direct_answer_summary.
    if not items:
        triage = build_investigation_triage_guidance(user_query)
        if triage:
            items = [
                line.strip().lstrip("- ").strip()
                for line in triage.splitlines()
                if line.strip().startswith("- ")
            ]

    updated = analyst_response.model_copy(
        update={
            "direct_answer_summary": lead[:2000],
            "one_sentence_finding": lead[:500],
            "investigation_steps": items[:12] or list(analyst_response.investigation_steps or []),
            "recommended_actions": items[:8] or list(analyst_response.recommended_actions or []),
            "analyst_checklist": items[:8] or list(analyst_response.analyst_checklist or []),
            "review_notice": None,
        }
    )
    return updated, ""


def _is_thin_guidance_stub(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return True
    if _THIN_GUIDANCE_STUB.search(body):
        return True
    return len(body.split()) < 40 and _CHECKLIST_MARKER not in body.lower()


def _lead_prose(summary: str, *, user_query: str, path_type: str | None) -> str:
    body = str(summary or "").strip()
    # Drop any checklist block already embedded in the summary.
    if _CHECKLIST_MARKER in body.lower():
        cut = body.lower().find(_CHECKLIST_MARKER)
        body = body[:cut].strip()
    if body and not _is_thin_guidance_stub(body):
        if _CHECKLIST_MARKER not in body.lower():
            return body[:1200]
    for line in summary.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.lower().startswith(_CHECKLIST_MARKER):
            break
        if cleaned.startswith("- "):
            continue
        return cleaned[:500]
    if path_type == "guided_investigation":
        return "Guided investigation prepared for analyst review; no live query was performed."
    triage = build_investigation_triage_guidance(user_query)
    if triage:
        first = next((ln.strip() for ln in triage.splitlines() if ln.strip() and not ln.strip().startswith("-")), "")
        if first:
            return first[:500]
    return "SOC investigation guidance prepared for analyst review; no live query was performed."


def _collect_guidance_items(
    *,
    analyst_response: AnalystResponseEnvelope,
    evidence_plan: dict[str, Any] | None,
    answer_contract: Any | None,
) -> list[str]:
    candidates: list[str] = []
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}

    def _extend(values: Any) -> None:
        if not isinstance(values, list):
            return
        for value in values:
            text = str(value).strip()
            if text:
                candidates.append(text)

    _extend(plan.get("checklist"))
    _extend(plan.get("investigation_workflow"))
    _extend(analyst_response.analyst_checklist)
    _extend(analyst_response.investigation_steps)
    _extend(analyst_response.recommended_actions)
    if answer_contract is not None:
        _extend(getattr(answer_contract, "analyst_checklist_safe", None))
        _extend(getattr(answer_contract, "investigation_steps", None))

    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.lower()
        if key in seen or key.startswith(_CHECKLIST_MARKER):
            continue
        seen.add(key)
        unique.append(item)
    return unique
