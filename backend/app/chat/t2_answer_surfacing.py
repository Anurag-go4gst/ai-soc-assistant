"""T2 answer surfacing — merge guidance package and expose SPL drafts (WS-2)."""

from __future__ import annotations

from typing import Any

from app.chat.answer_shape_router import classify_answer_shape, shape_suppresses_spl, should_bypass_shape_router
from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.schemas.responses import AnalystResponseEnvelope
from app.spl.draft_preview import DRAFT_PREVIEW_STATUS_MESSAGE, build_draft_preview_analyst_message


_HIL_KIND_COPY: dict[str, str] = {
    "spl_source_profile_clarification": "Confirm index/sourcetype for this draft before review.",
    "execution_approval": "Analyst approval is required before any Splunk search execution.",
    "intent_clarification": "Additional context is required before proceeding.",
    "answer_guard_blocked": "Answer Guard blocked the draft — review the technical trace.",
    "session_context_stale": "Session context is stale — repeat alert context or start fresh.",
}

_DRAFT_PREVIEW_OWNERSHIP_MARKERS = (
    "lab-only draft spl preview",
    "soc review checklist",
    "hil/soc review is required",
)


def human_review_kind_to_analyst_copy(kind: str | None, fallback: str | None = None) -> str:
    if not kind:
        return str(fallback or "Human-in-the-loop review is required before execution.")
    return _HIL_KIND_COPY.get(str(kind), str(fallback or "Analyst review is required before execution."))


def _has_spl_artifact(
    *,
    candidate_spl: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> bool:
    if isinstance(spl_draft_preview, dict) and str(spl_draft_preview.get("draft_spl") or "").strip():
        return True
    if isinstance(candidate_spl, dict) and str(candidate_spl.get("candidate_spl") or "").strip():
        return True
    if isinstance(spl_validation, dict) and str(spl_validation.get("normalized_spl") or spl_validation.get("candidate_spl") or "").strip():
        return True
    return False


def enhance_answer_contract_for_t2_surfacing(
    contract: AnswerContract,
    *,
    candidate_spl: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    user_query: str,
    match_path: str | None,
    resource_plan: dict[str, Any] | None = None,
) -> AnswerContract:
    if not settings.ai_soc_t2_answer_surfacing_enabled or should_bypass_shape_router(match_path):
        return contract
    shape = classify_answer_shape(user_query, resource_plan=resource_plan).primary_shape
    if shape_suppresses_spl(shape):
        render = dict(contract.render_sections)
        render["spl_artifact"] = False
        return contract.model_copy(update={"render_sections": render, "spl_present": False, "spl_status": "not_required"})
    if not _has_spl_artifact(
        candidate_spl=candidate_spl,
        spl_draft_preview=spl_draft_preview,
        spl_validation=spl_validation,
    ):
        return contract
    render = dict(contract.render_sections)
    render["spl_artifact"] = True
    render["draft_spl_preview"] = bool(
        isinstance(spl_draft_preview, dict) and str(spl_draft_preview.get("draft_spl") or "").strip()
    )
    section_order = list(contract.section_order)
    if "spl_artifact" not in section_order:
        section_order.append("spl_artifact")
    spl_status = contract.spl_status if contract.spl_status != "not_required" else "review_required"
    return contract.model_copy(
        update={
            "render_sections": render,
            "spl_present": True,
            "spl_status": spl_status,
            "section_order": section_order,
        }
    )


def build_merged_t2_message(
    *,
    guidance_text: str,
    human_review: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    limitations: list[str] | None = None,
    user_query: str,
    match_path: str | None,
    resource_plan: dict[str, Any] | None = None,
) -> str:
    if not settings.ai_soc_t2_answer_surfacing_enabled or should_bypass_shape_router(match_path):
        return guidance_text
    shape = classify_answer_shape(user_query, resource_plan=resource_plan).primary_shape
    parts: list[str] = [guidance_text.strip()] if guidance_text and guidance_text.strip() else []
    if not shape_suppresses_spl(shape):
        if isinstance(spl_draft_preview, dict) and str(spl_draft_preview.get("draft_spl") or "").strip():
            draft_spl = str(spl_draft_preview.get("draft_spl") or "").strip()
            code_block = f"Draft SPL (review-only, not executed):\n```\n{draft_spl}\n```"
            if _guidance_already_owns_draft_preview(guidance_text):
                parts.append(code_block)
            else:
                draft_block = build_draft_preview_analyst_message(spl_draft_preview)
                parts.append(f"{draft_block}\n\n{code_block}")
        elif isinstance(candidate_spl, dict) and str(candidate_spl.get("candidate_spl") or "").strip():
            parts.append(
                "Candidate SPL draft (review-only, not executed):\n"
                f"```\n{candidate_spl['candidate_spl'].strip()}\n```"
            )
        elif isinstance(spl_validation, dict) and str(spl_validation.get("normalized_spl") or "").strip():
            parts.append(
                "Governed SPL draft (validated, not executed):\n"
                f"```\n{spl_validation['normalized_spl'].strip()}\n```"
            )
    if limitations:
        lim_lines = [str(item) for item in limitations if str(item).strip()]
        if lim_lines:
            parts.append("Limitations:\n" + "\n".join(f"- {line}" for line in lim_lines))
    review = human_review if isinstance(human_review, dict) else {}
    if review.get("required"):
        kind = str(review.get("review_type") or review.get("kind") or "")
        hil_copy = human_review_kind_to_analyst_copy(kind, review.get("safe_message_for_user"))
        parts.append(f"Review package: {hil_copy}")
    elif isinstance(spl_draft_preview, dict) and not _guidance_already_owns_draft_preview(guidance_text):
        parts.append(f"Review package: {DRAFT_PREVIEW_STATUS_MESSAGE}")
    merged = "\n\n".join(part for part in parts if part)
    return merged or guidance_text


def _guidance_already_owns_draft_preview(guidance_text: str) -> bool:
    lowered = str(guidance_text or "").lower()
    return any(marker in lowered for marker in _DRAFT_PREVIEW_OWNERSHIP_MARKERS)


def _summary_for_t2_section_plan(
    *,
    guidance_text: str,
    spl_draft_preview: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    user_query: str,
    match_path: str | None,
    resource_plan: dict[str, Any] | None = None,
) -> str:
    """Single-owner card summary for T2 review-only answers.

    ``message`` may remain a merged markdown fallback for simple clients, but the
    structured analyst card already owns SPL, checklist, and limitation sections.
    Keep the summary short so those producers do not all render twice.
    """
    shape = classify_answer_shape(user_query, resource_plan=resource_plan).primary_shape
    if shape_suppresses_spl(shape):
        return "Knowledge-only guidance prepared for analyst review; no SPL was generated."
    has_spl = _has_spl_artifact(
        candidate_spl=candidate_spl,
        spl_draft_preview=spl_draft_preview,
        spl_validation=spl_validation,
    )
    if has_spl:
        if isinstance(spl_draft_preview, dict) and str(spl_draft_preview.get("draft_spl") or "").strip():
            return "Review-only SPL draft - no live query was executed."
        if isinstance(spl_validation, dict) and str(spl_validation.get("normalized_spl") or "").strip():
            return "Governed SPL draft prepared for analyst review; it has not been executed."
        return "Candidate SPL draft prepared for analyst review; it has not been executed."
    if str(match_path or "") in {"out_of_registry", "query_understanding_weak"}:
        return "Guided investigation prepared for analyst review; no live query was executed."
    first_line = next((line.strip() for line in guidance_text.splitlines() if line.strip()), "")
    return first_line[:300] or "Analyst guidance prepared for review."


def apply_t2_answer_surfacing(
    *,
    message: str,
    answer_contract: AnswerContract | None,
    analyst_response: AnalystResponseEnvelope | None,
    human_review: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    user_query: str,
    match_path: str | None,
    resource_plan: dict[str, Any] | None = None,
) -> tuple[str, AnswerContract | None, AnalystResponseEnvelope | None]:
    if not settings.ai_soc_t2_answer_surfacing_enabled or should_bypass_shape_router(match_path):
        return message, answer_contract, analyst_response
    limitations = list(answer_contract.limitations) if answer_contract is not None else []
    merged_message = build_merged_t2_message(
        guidance_text=message,
        human_review=human_review,
        spl_draft_preview=spl_draft_preview,
        candidate_spl=candidate_spl,
        spl_validation=spl_validation,
        limitations=limitations,
        user_query=user_query,
        match_path=match_path,
        resource_plan=resource_plan,
    )
    updated_contract = answer_contract
    if answer_contract is not None:
        updated_contract = enhance_answer_contract_for_t2_surfacing(
            answer_contract,
            candidate_spl=candidate_spl,
            spl_draft_preview=spl_draft_preview,
            spl_validation=spl_validation,
            user_query=user_query,
            match_path=match_path,
            resource_plan=resource_plan,
        )
    updated_response = analyst_response
    if analyst_response is not None and updated_contract is not None:
        from app.chat.final_answer_readability import apply_final_answer_readability

        updated_response = apply_final_answer_readability(analyst_response, updated_contract)
        summary = _summary_for_t2_section_plan(
            guidance_text=message,
            spl_draft_preview=spl_draft_preview,
            candidate_spl=candidate_spl,
            spl_validation=spl_validation,
            user_query=user_query,
            match_path=match_path,
            resource_plan=resource_plan,
        )
        if summary:
            updated_response = updated_response.model_copy(update={"direct_answer_summary": summary[:500]})
        from app.chat.guidance_envelope import populate_envelope_from_guidance
        from app.chat.t2_review_checklist import is_t2_spl_native_candidate

        if not is_t2_spl_native_candidate(candidate_spl):
            updated_response = populate_envelope_from_guidance(
                updated_response, message, limitations=limitations
            )
    return merged_message, updated_contract, updated_response
