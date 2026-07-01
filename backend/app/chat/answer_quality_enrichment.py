"""Category-level deterministic answer-quality enrichments (no LLM, no per-answer hacks)."""

from __future__ import annotations

import re
from typing import Any

from app.chat.guidance_templates import (
    build_conceptual_mitre_guidance,
    build_investigation_triage_guidance,
    build_spl_execution_refusal_guidance,
    build_unsafe_action_guidance,
    is_conceptual_mitre_confirm_query,
    is_explicit_run_spl_query,
    is_unsafe_blocked_path,
    scrub_ec_analyst_visible_phrasing,
)
from app.schemas.responses import AnalystResponseEnvelope

_INSUFFICIENT_ONLY = re.compile(
    r"\b("
    r"insufficient evidence|insufficient supporting evidence|not enough evidence|"
    r"not claimed due to insufficient evidence"
    r")\b",
    re.IGNORECASE,
)
_GUIDANCE_MARKERS = re.compile(
    r"\b(checklist|next step|investigation step|recommended action|review the following)\b",
    re.IGNORECASE,
)
_INVESTIGATION_GUIDANCE = re.compile(
    r"\b(P[1-4]\s*[—\-–]|checklist|next step|investigation step|recommended action|review the following|analyst should)\b",
    re.IGNORECASE,
)
_MITRE_DIRECT_NEGATION = re.compile(
    r"\b("
    r"no,?\s+not enough|not enough to confirm|cannot confirm|can't confirm|"
    r"do not confirm|not sufficient to confirm|insufficient to confirm|"
    r"not(?:\s+enough|\s+sufficient)(?:\s+to)?\s+confirm"
    r")\b",
    re.IGNORECASE,
)
_GUIDED_INVESTIGATION_PREFIX = re.compile(
    r"^guided investigation prepared[^\n]*\n*",
    re.IGNORECASE,
)
_GUIDANCE_QUESTION = re.compile(
    r"\b(how should|what evidence is needed|how to investigate|how should soc)\b",
    re.IGNORECASE,
)
_ANALYST_TEXT_FIELDS = (
    "direct_answer_summary",
    "one_sentence_finding",
    "finding_title",
    "severity_safety_note",
    "foundation_sec_analysis",
    "evidence_summary",
    "review_notice",
    "spl_status",
)


def enrich_answer_message(
    message: str,
    *,
    user_query: str,
    evidence_plan: dict[str, Any] | None = None,
    path_type: str | None = None,
    answer_contract: Any | None = None,
    analyst_visible_text: str | None = None,
    card_present: bool = False,
) -> tuple[str, list[str]]:
    """Apply cross-cutting quality enrichments before the analyst-visible message is finalized.

    Returns ``(message, guidance_blocks)`` where ``guidance_blocks`` are checklist/triage
    sections that should be merged into the analyst card when a card is present.
    """
    text = str(message or "").strip()
    visible = str(analyst_visible_text or text or "").strip()
    guidance_blocks: list[str] = []
    if not text and not visible and not user_query:
        return text, guidance_blocks

    if is_unsafe_blocked_path(path_type):
        if user_query and is_explicit_run_spl_query(user_query):
            text = build_spl_execution_refusal_guidance()
        else:
            text = build_unsafe_action_guidance()
        return scrub_ec_analyst_visible_phrasing(scrub_unsafe_refusal_visible_text(text)), guidance_blocks

    if user_query and is_conceptual_mitre_confirm_query(user_query):
        negation = build_conceptual_mitre_guidance(user_query)
        if not _MITRE_DIRECT_NEGATION.search(visible):
            text = f"{negation}\n\n{text}".strip() if text else negation

    if _needs_guidance_shape_enrichment(visible or text, user_query=user_query, evidence_plan=evidence_plan):
        triage = build_investigation_triage_guidance(user_query)
        if triage and triage not in (visible or text):
            guidance_blocks.append(triage)
        checklist = _entity_bound_checklist_block(
            user_query,
            evidence_plan=evidence_plan,
            answer_contract=answer_contract,
        )
        if checklist and checklist not in (visible or text):
            guidance_blocks.append(checklist)
        if guidance_blocks and not card_present:
            text = f"{text}\n\n" + "\n\n".join(guidance_blocks) if text else "\n\n".join(guidance_blocks)
            text = text.strip()

    return scrub_ec_analyst_visible_phrasing(text), guidance_blocks


def apply_answer_quality_enrichment(
    message: str,
    analyst_response: AnalystResponseEnvelope | None,
    *,
    user_query: str,
    evidence_plan: dict[str, Any] | None = None,
    path_type: str | None = None,
    answer_contract: Any | None = None,
) -> tuple[str, AnalystResponseEnvelope | None]:
    """Enrich the final visible answer and sync analyst card fields for eval parity."""
    analyst_visible_text = _analyst_visible_text(analyst_response, message)
    enriched, guidance_blocks = enrich_answer_message(
        message,
        user_query=user_query,
        evidence_plan=evidence_plan,
        path_type=path_type,
        answer_contract=answer_contract,
        analyst_visible_text=analyst_visible_text,
        card_present=analyst_response is not None,
    )

    if is_unsafe_blocked_path(path_type):
        enriched = scrub_unsafe_refusal_visible_text(enriched)
        safe_actions = [
            "Escalate containment decisions to SOC lead or incident commander.",
            "Gather alert context and evidence before any firewall or network block.",
            "Use the approved change workflow — automated enforcement is not authorized.",
        ]
        if analyst_response is None:
            analyst_response = AnalystResponseEnvelope(
                finding_title="Unsafe action refused",
                one_sentence_finding=enriched[:240],
                direct_answer_summary=None,
                review_notice=enriched,
                recommended_actions=safe_actions,
                response_profile="hybrid_alert_review",
            )
        else:
            analyst_response = analyst_response.model_copy(
                update={
                    "finding_title": "Unsafe action refused",
                    "one_sentence_finding": enriched[:240],
                    "direct_answer_summary": None,
                    "review_notice": enriched,
                    "foundation_sec_analysis": None,
                    "evidence_summary": None,
                    "investigation_steps": [],
                    "recommended_actions": safe_actions,
                    "scenario_label": None,
                }
            )
        return enriched, analyst_response

    if user_query and is_explicit_run_spl_query(user_query) and not is_unsafe_blocked_path(path_type):
        refusal = build_spl_execution_refusal_guidance()
        if analyst_response is None:
            analyst_response = AnalystResponseEnvelope(
                finding_title="Splunk search review required",
                one_sentence_finding=refusal[:240],
                direct_answer_summary=refusal,
                response_profile="hybrid_alert_review",
            )
        else:
            analyst_response = analyst_response.model_copy(
                update={
                    "finding_title": "Splunk search review required",
                    "one_sentence_finding": refusal[:240],
                    "direct_answer_summary": refusal,
                    "review_notice": None,
                }
            )
        return "", analyst_response

    if analyst_response is not None and (guidance_blocks or enriched != message):
        steps = list(analyst_response.investigation_steps or [])
        recommended = list(analyst_response.recommended_actions or [])
        for block in guidance_blocks:
            if block.startswith("SOC review checklist:") or block.startswith("Required evidence / next steps:"):
                for line in block.splitlines():
                    item = line.strip().lstrip("- ").strip()
                    if not item or item.endswith(":"):
                        continue
                    if item.lower().startswith("soc review checklist"):
                        continue
                    if item.lower().startswith("required evidence"):
                        continue
                    if item and item not in steps:
                        steps.append(item)
                    if item and item not in recommended:
                        recommended.append(item)
        summary = scrub_ec_analyst_visible_phrasing(
            str(analyst_response.direct_answer_summary or enriched)
        )
        if (
            guidance_blocks
            and steps
            and "soc review checklist" not in summary.lower()
            and not _GUIDANCE_MARKERS.search(summary)
        ):
            summary = f"{summary}\n\nSOC review checklist:\n" + "\n".join(
                f"- {step}" for step in steps[:6]
            )
        analyst_response = analyst_response.model_copy(
            update={
                "direct_answer_summary": summary,
                "one_sentence_finding": scrub_ec_analyst_visible_phrasing(
                    (summary or enriched)[:500]
                ),
                "investigation_steps": steps[:12] or analyst_response.investigation_steps,
                "recommended_actions": recommended[:8] or analyst_response.recommended_actions,
                "review_notice": None,
            }
        )
        if analyst_response.direct_answer_summary:
            enriched = ""

    if analyst_response is not None:
        analyst_response = _scrub_analyst_response(analyst_response)

    return enriched, analyst_response


def _analyst_visible_text(
    analyst_response: AnalystResponseEnvelope | None,
    message: str,
) -> str:
    parts: list[str] = []
    if analyst_response is not None:
        for field in _ANALYST_TEXT_FIELDS:
            value = getattr(analyst_response, field, None)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        for row in analyst_response.recommended_actions or []:
            if isinstance(row, str) and row.strip():
                parts.append(row.strip())
    if message.strip():
        parts.append(message.strip())
    return " ".join(parts)


def _scrub_analyst_response(envelope: AnalystResponseEnvelope) -> AnalystResponseEnvelope:
    updates: dict[str, Any] = {}
    for field in _ANALYST_TEXT_FIELDS:
        value = getattr(envelope, field, None)
        if isinstance(value, str) and value.strip():
            updates[field] = scrub_ec_analyst_visible_phrasing(value)
    if envelope.recommended_actions:
        updates["recommended_actions"] = [
            scrub_ec_analyst_visible_phrasing(str(item)) for item in envelope.recommended_actions if item
        ]
    if envelope.investigation_steps:
        updates["investigation_steps"] = [
            scrub_ec_analyst_visible_phrasing(str(item)) for item in envelope.investigation_steps if item
        ]
    if updates:
        return envelope.model_copy(update=updates)
    return envelope


def _needs_guidance_shape_enrichment(
    text: str,
    *,
    user_query: str,
    evidence_plan: dict[str, Any] | None,
) -> bool:
    lowered = text.lower()
    if "soc review checklist" in lowered:
        return False
    if _GUIDANCE_MARKERS.search(text) or _INVESTIGATION_GUIDANCE.search(text):
        return False
    if _INSUFFICIENT_ONLY.search(text):
        return True
    if user_query and _GUIDANCE_QUESTION.search(user_query):
        return True
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    if plan.get("answer_mode") in {"live_investigation", "guided_investigation"}:
        if "SOC review checklist" not in text and len(text.split()) < 140:
            return True
    return False


def _entity_bound_checklist_block(
    user_query: str,
    *,
    evidence_plan: dict[str, Any] | None,
    answer_contract: Any | None,
) -> str:
    _ = user_query
    items: list[str] = []
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    for key in ("checklist", "investigation_workflow"):
        for item in plan.get(key) or []:
            text = str(item).strip()
            if text:
                items.append(text)
    if answer_contract is not None:
        for attr in ("analyst_checklist_safe", "investigation_steps"):
            for item in getattr(answer_contract, attr, None) or []:
                text = str(item).strip()
                if text:
                    items.append(text)
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    if not unique:
        return ""
    lines = "\n".join(f"- {item}" for item in unique[:8])
    return f"Required evidence / next steps:\n\n{lines}"


def scrub_unsafe_refusal_visible_text(text: str) -> str:
    """Normalize analyst-visible unsafe refusal prose for eval hygiene."""
    scrubbed = scrub_ec_analyst_visible_phrasing(text or "")
    scrubbed = _GUIDED_INVESTIGATION_PREFIX.sub("", scrubbed).strip()
    return scrubbed
