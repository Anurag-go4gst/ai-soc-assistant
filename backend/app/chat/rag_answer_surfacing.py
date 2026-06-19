"""RAG / playbook surfacing for knowledge-only turns (WS-7a)."""

from __future__ import annotations

from typing import Any

from app.chat.analyst_response_builder import _playbook_from_rag
from app.chat.answer_shape_router import (
    _regulatory_knowledge_guidance,
    is_regulatory_reporting_query,
)
from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.evidence.context_sufficiency import KNOWLEDGE_ONLY_ANSWER
from app.schemas.responses import AnalystResponseEnvelope

REGULATORY_DISCLAIMER = (
    "Disclaimer: verify reporting timelines and obligations with compliance/CISO — "
    "this assistant is not legal authority. No Splunk search was generated for this "
    "reporting-obligation question."
)

_RAG_STUB_PHRASES = (
    "spl and mcp are skipped",
    "governed knowledge path selected",
    "governed knowledge checklist path selected",
    "no governed kb/sop match",
)


def is_knowledge_answer_mode(
    answer_mode: str | None,
    context_sufficiency_status: str | None,
) -> bool:
    mode = str(answer_mode or "").strip()
    status = str(context_sufficiency_status or "").strip()
    return mode == "rag_only" or status == KNOWLEDGE_ONLY_ANSWER


def has_rag_playbook_hits(source_evidence: list[dict[str, Any]] | None) -> bool:
    playbook, sop_guidance, _ = _playbook_from_rag(source_evidence or [])
    if playbook is None:
        return False
    steps = list((sop_guidance or {}).get("triage_steps") or [])
    return bool(steps or playbook.get("title") or playbook.get("purpose"))


def build_rag_knowledge_message(
    playbook: dict[str, Any] | None,
    sop_guidance: dict[str, Any] | None,
    *,
    regulatory: bool = False,
) -> str:
    title = str((playbook or {}).get("title") or "SOC knowledge guidance")
    purpose = str((playbook or {}).get("purpose") or "").strip()
    steps = [str(item).strip() for item in (sop_guidance or {}).get("triage_steps") or [] if str(item).strip()]
    parts: list[str] = [title]
    if purpose:
        parts.append(purpose)
    if steps:
        numbered = "\n".join(f"{index}. {step}" for index, step in enumerate(steps[:8], start=1))
        parts.append(f"SOC review checklist:\n{numbered}")
    if regulatory:
        parts.append(REGULATORY_DISCLAIMER)
    else:
        parts.append("Knowledge-only path — no Splunk search or MCP execution was performed.")
    return "\n\n".join(part for part in parts if part)


def is_rag_stub_message(message: str | None) -> bool:
    lowered = str(message or "").lower()
    return any(phrase in lowered for phrase in _RAG_STUB_PHRASES)


def _normalize_knowledge_human_review(human_review: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(human_review, dict):
        return human_review
    if human_review.get("required"):
        return human_review
    review_type = str(human_review.get("review_type") or human_review.get("kind") or "")
    if review_type in {"execution_approval", "none", ""}:
        return {
            **human_review,
            "required": False,
            "review_type": "none",
            "reason": "knowledge_only_no_execution",
        }
    return human_review


def _enhance_contract_for_rag_surfacing(contract: AnswerContract) -> AnswerContract:
    render = dict(contract.render_sections)
    render["policy_citation"] = True
    render["procedural_steps"] = True
    section_order = list(contract.section_order)
    for section in ("policy_citation", "procedural_steps"):
        if section not in section_order:
            section_order.append(section)
    return contract.model_copy(
        update={
            "render_sections": render,
            "spl_present": False,
            "spl_status": "not_required",
            "section_order": section_order,
        }
    )


def apply_rag_answer_surfacing(
    *,
    message: str,
    answer_contract: AnswerContract | None,
    analyst_response: AnalystResponseEnvelope | None,
    source_evidence: list[dict[str, Any]] | None,
    evidence_plan: dict[str, Any] | None,
    context_sufficiency: dict[str, Any] | None,
    user_query: str,
    human_review: dict[str, Any] | None,
) -> tuple[str, AnswerContract | None, AnalystResponseEnvelope | None, dict[str, Any] | None]:
    if not settings.ai_soc_t2_rag_surfacing_enabled:
        return message, answer_contract, analyst_response, human_review

    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    sufficiency = context_sufficiency if isinstance(context_sufficiency, dict) else {}
    knowledge_turn = is_knowledge_answer_mode(
        str(plan.get("answer_mode") or ""),
        str(sufficiency.get("status") or ""),
    )
    if not knowledge_turn:
        return message, answer_contract, analyst_response, human_review

    updated_review = _normalize_knowledge_human_review(human_review)
    regulatory = is_regulatory_reporting_query(user_query)
    if not has_rag_playbook_hits(source_evidence):
        if regulatory and is_rag_stub_message(message):
            surfaced_message = _regulatory_knowledge_guidance(user_query)
            updated_contract = answer_contract
            if answer_contract is not None:
                updated_contract = _enhance_contract_for_rag_surfacing(answer_contract)
            updated_response = analyst_response
            if analyst_response is not None and updated_contract is not None:
                updated_response = analyst_response.model_copy(
                    update={"direct_answer_summary": surfaced_message[:2000]}
                )
                from app.chat.final_answer_readability import apply_final_answer_readability

                updated_response = apply_final_answer_readability(updated_response, updated_contract)
            return surfaced_message, updated_contract, updated_response, updated_review
        return message, answer_contract, analyst_response, updated_review

    playbook, sop_guidance, rag_meta = _playbook_from_rag(source_evidence or [])
    surfaced_message = build_rag_knowledge_message(
        playbook,
        sop_guidance,
        regulatory=regulatory,
    )

    updated_message = surfaced_message
    if message and not is_rag_stub_message(message):
        updated_message = message

    updated_contract = answer_contract
    if answer_contract is not None:
        updated_contract = _enhance_contract_for_rag_surfacing(answer_contract)

    updated_response = analyst_response
    if analyst_response is not None and updated_contract is not None:
        enriched_playbook = dict(playbook or {})
        if rag_meta:
            enriched_playbook.update({key: value for key, value in rag_meta.items() if value is not None})
        updated_response = analyst_response.model_copy(
            update={
                "retrieved_playbook": enriched_playbook or analyst_response.retrieved_playbook,
                "sop_guidance": sop_guidance or analyst_response.sop_guidance,
                "direct_answer_summary": updated_message[:2000],
            }
        )
        from app.chat.final_answer_readability import apply_final_answer_readability

        updated_response = apply_final_answer_readability(updated_response, updated_contract)
        summary = updated_response.direct_answer_summary
        if summary:
            updated_response = updated_response.model_copy(update={"direct_answer_summary": summary[:2000]})

    return updated_message, updated_contract, updated_response, updated_review
