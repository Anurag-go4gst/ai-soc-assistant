"""Phase 9 governed LLM answer composer.

Narrates analyst-visible prose only from the enriched AnswerContract and a
sanitized enrichment projection. The model is non-authoritative; any unsafe or
unsupported output falls back to the deterministic Phase 8 envelope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.schemas.responses import AnalystResponseEnvelope

_SYSTEM_PROMPT = (
    "You are a SOC analyst assistant. You will receive a GOVERNED ANSWER CONTRACT "
    "with deterministic facts already decided by the security pipeline.\n"
    "Write 2-4 sentences of plain analyst prose that restates ONLY those facts.\n"
    "Hard rules:\n"
    "- Do not invent severity, MITRE status upgrades, SPL approval, execution, "
    "or compromise conclusions.\n"
    "- Candidate MITRE techniques stay candidate; only evidence-supported "
    "techniques may be described as evidence-supported.\n"
    "- SPL is review-only unless the contract explicitly says it was executed.\n"
    "- Preserve missing-evidence and limitation caveats.\n"
    "- If human review is required, say review is required.\n"
    "- No SPL queries, no tool instructions, no GitHub references.\n"
    "- Output plain prose only."
)

_GITHUB_MARKERS = ("skill.md", "github.com", "/skills/", "github_ref:")
_EXECUTED_SPL = re.compile(r"\b(spl (was )?executed|executed spl|executed in splunk)\b", re.IGNORECASE)
_APPROVED_EXEC = re.compile(
    r"\b(spl (is )?approved for execution|approved for execution|ready to execute|execute (the )?spl)\b",
    re.IGNORECASE,
)
_COMPROMISE = re.compile(
    r"\b(account compromis\w*|confirmed compromis\w*|compromise confirmed)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(not confirmed|no evidence of|not evidence of|candidate only|is not confirmed|review required|do not claim)\b",
    re.IGNORECASE,
)
_EVIDENCE_SUPPORTED = re.compile(r"\b(evidence[- ]supported|evidence supported)\b", re.IGNORECASE)
_SEVERITY_TOKEN = re.compile(r"\bP[1-4]\b", re.IGNORECASE)


@dataclass(frozen=True)
class GovernedComposerResult:
    envelope: AnalystResponseEnvelope
    llm_composer_enabled: bool
    llm_composer_used: bool
    llm_guard_status: str
    llm_fallback_used: bool
    llm_blocked_reason: str | None = None

    def trace_payload(self) -> dict[str, Any]:
        return {
            "llm_composer_enabled": self.llm_composer_enabled,
            "llm_composer_used": self.llm_composer_used,
            "llm_guard_status": self.llm_guard_status,
            "llm_fallback_used": self.llm_fallback_used,
            "llm_blocked_reason": self.llm_blocked_reason,
        }


def composer_is_enabled() -> bool:
    return (
        settings.control_plane_enabled
        and settings.ai_soc_llm_final_synthesis_enabled
        and settings.ai_soc_llm_live_synthesis_enabled
    )


def build_composer_prompt(
    contract: AnswerContract,
    enrichment_projection: dict[str, Any] | None,
) -> str:
    """Build a contract-only composer prompt (no raw events or GitHub content)."""
    projection = enrichment_projection or {}
    checklist = list(contract.analyst_checklist_safe)
    if not checklist:
        checklist = [str(item) for item in projection.get("analyst_checklist") or [] if item]
    answer_rules = list(contract.answer_rules_applied)
    if not answer_rules:
        answer_rules = [str(item) for item in projection.get("answer_rules") or [] if item]
    limitations = list(contract.limitations)
    if not limitations:
        limitations = [str(item) for item in projection.get("limitations") or [] if item]

    lines = ["GOVERNED ANSWER CONTRACT:"]
    if contract.severity_label:
        lines.append(f"- Severity (deterministic): {contract.severity_label}")
    lines.append(f"- SPL status: {contract.spl_status}")
    lines.append(f"- HIL status: {contract.hil_status}")
    if contract.execution_status_display:
        lines.append(f"- Execution status: {contract.execution_status_display}")
    elif contract.execution_status_label:
        lines.append(f"- Execution status: {contract.execution_status_label}")

    if contract.missing_evidence:
        lines.append("- Missing evidence: " + "; ".join(contract.missing_evidence))
    if limitations:
        lines.append("- Limitations: " + "; ".join(limitations))
    if checklist:
        lines.append("- Analyst checklist: " + "; ".join(checklist))
    if answer_rules:
        lines.append("- Answer rules: " + "; ".join(answer_rules))
    if contract.unsupported_claims_avoid:
        lines.append("- Do not claim: " + "; ".join(contract.unsupported_claims_avoid))
    if contract.assumptions:
        lines.append("- Assumptions: " + "; ".join(contract.assumptions))

    _append_mitre_bucket(lines, "Candidate MITRE (metadata only)", contract.candidate_mitre)
    _append_mitre_bucket(lines, "Evidence-supported MITRE", contract.evidence_supported_mitre)
    _append_mitre_bucket(lines, "Requires validation MITRE", contract.requires_validation_mitre)
    _append_mitre_bucket(lines, "Not claimed MITRE", contract.not_claimed_mitre)
    _append_mitre_bucket(lines, "Ruled out MITRE", contract.ruled_out_mitre)
    if contract.mitre_technique_ids:
        lines.append("- Visible MITRE technique IDs: " + ", ".join(contract.mitre_technique_ids))

    if contract.human_review_required or contract.hil_status in {
        "required",
        "clarification_required",
        "missing_evidence_review",
    }:
        lines.append("- Human review: required before any execution or destructive action.")

    lines.append("\nWrite the analyst summary now using only the contract facts above.")
    return "\n".join(lines)


def validate_composed_prose(text: str, contract: AnswerContract) -> tuple[bool, str | None]:
    """Fail closed when composed prose contradicts the AnswerContract."""
    lowered = " ".join(text.split()).lower()
    if not lowered.strip():
        return False, "Composer returned empty prose."

    for marker in _GITHUB_MARKERS:
        if marker in lowered:
            return False, f"Composed prose includes forbidden provenance marker: {marker}"

    supported = {tid.upper() for tid in contract.evidence_supported_mitre}
    candidate = {tid.upper() for tid in contract.candidate_mitre}
    allowed_techniques = supported | candidate | {tid.upper() for tid in contract.requires_validation_mitre}
    allowed_techniques |= {tid.upper() for tid in contract.mitre_technique_ids}

    if _EVIDENCE_SUPPORTED.search(lowered):
        for tid in candidate:
            if tid.upper() not in supported and tid.lower() in lowered:
                return False, f"Candidate MITRE {tid} was upgraded to evidence-supported in prose."

    for tid in allowed_techniques:
        if tid and tid not in supported and _technique_claims_evidence_supported(lowered, tid):
            return False, f"MITRE {tid} described as evidence-supported without contract support."

    for tid in re.findall(r"\bT\d{4}(?:\.\d{3})?\b", text, flags=re.IGNORECASE):
        if tid.upper() not in allowed_techniques and tid.upper() not in {
            x.upper() for x in contract.not_claimed_mitre
        } | {x.upper() for x in contract.ruled_out_mitre}:
            return False, f"Composed prose introduces unsupported MITRE technique {tid.upper()}."

    if _COMPROMISE.search(lowered) and not _NEGATION.search(lowered):
        blocked_claims = {str(item).lower() for item in contract.unsupported_claims_avoid}
        if "account_compromise" in blocked_claims or "account compromis" in blocked_claims:
            return False, "Composed prose claims compromise without contract support."

    exec_label = str(contract.execution_status_label or "")
    if _EXECUTED_SPL.search(lowered) and exec_label not in {"executed_mock_evidence", "executed_live_evidence"}:
        return False, "Composed prose claims SPL execution without contract support."

    if _APPROVED_EXEC.search(lowered):
        return False, "Composed prose claims SPL approval or execution eligibility."

    contract_severity = _severity_token(contract.severity_label)
    prose_severity = _severity_tokens_in_text(text)
    if contract_severity and prose_severity and contract_severity not in prose_severity:
        return False, "Composed prose invents a severity level not present in the contract."

    if contract.human_review_required or contract.hil_status in {"required", "clarification_required"}:
        if not _NEGATION.search(lowered) and "review" not in lowered:
            return False, "Composed prose ignored required human review status."

    if contract.missing_evidence and not _mentions_missing_evidence(lowered, contract.missing_evidence):
        return False, "Composed prose removed required missing-evidence caveats."

    if contract.limitations and not _mentions_limitations(lowered, contract.limitations):
        return False, "Composed prose removed required limitations."

    return True, None


def compose_governed_answer(
    *,
    contract: AnswerContract,
    enrichment_projection: dict[str, Any] | None,
    fallback_envelope: AnalystResponseEnvelope,
    client: LocalChatClient | None = None,
) -> GovernedComposerResult:
    """Compose governed prose or return the Phase 8 deterministic envelope."""
    if not composer_is_enabled():
        return GovernedComposerResult(
            envelope=fallback_envelope,
            llm_composer_enabled=False,
            llm_composer_used=False,
            llm_guard_status="disabled",
            llm_fallback_used=False,
        )

    prompt = build_composer_prompt(contract, enrichment_projection)
    llm_client = client or build_synthesis_client_from_settings()
    if llm_client is None:
        return GovernedComposerResult(
            envelope=fallback_envelope,
            llm_composer_enabled=True,
            llm_composer_used=False,
            llm_guard_status="skipped",
            llm_fallback_used=True,
            llm_blocked_reason="Live LLM client is not configured.",
        )

    try:
        result = llm_client.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=min(settings.ai_soc_llm_max_output_tokens, 320),
            temperature=settings.ai_soc_llm_temperature,
        )
    except LocalChatError as exc:
        return GovernedComposerResult(
            envelope=fallback_envelope,
            llm_composer_enabled=True,
            llm_composer_used=False,
            llm_guard_status="skipped",
            llm_fallback_used=True,
            llm_blocked_reason=exc.user_message,
        )

    composed = result.text.strip()
    passed, blocked_reason = validate_composed_prose(composed, contract)
    if not passed:
        return GovernedComposerResult(
            envelope=fallback_envelope,
            llm_composer_enabled=True,
            llm_composer_used=False,
            llm_guard_status="blocked",
            llm_fallback_used=True,
            llm_blocked_reason=blocked_reason,
        )

    payload = fallback_envelope.model_dump()
    payload["direct_answer_summary"] = composed[:1200]
    return GovernedComposerResult(
        envelope=AnalystResponseEnvelope.model_validate(payload),
        llm_composer_enabled=True,
        llm_composer_used=True,
        llm_guard_status="passed",
        llm_fallback_used=False,
    )


def _append_mitre_bucket(lines: list[str], label: str, values: list[str]) -> None:
    if values:
        lines.append(f"- {label}: " + ", ".join(values))


def _technique_claims_evidence_supported(text: str, technique_id: str) -> bool:
    tid = technique_id.lower()
    if tid not in text:
        return False
    window = text[max(0, text.index(tid) - 80) : text.index(tid) + 80]
    return bool(_EVIDENCE_SUPPORTED.search(window))


def _severity_token(label: str | None) -> str | None:
    if not label:
        return None
    match = _SEVERITY_TOKEN.search(label)
    return match.group(0).upper() if match else None


def _severity_tokens_in_text(text: str) -> set[str]:
    return {token.upper() for token in _SEVERITY_TOKEN.findall(text)}


def _mentions_missing_evidence(text: str, missing: list[str]) -> bool:
    if "missing evidence" in text or "missing/unavailable evidence" in text:
        return True
    hits = 0
    for item in missing:
        tokens = [part for part in re.split(r"[_\s]+", str(item).lower()) if len(part) >= 4]
        if any(token in text for token in tokens):
            hits += 1
    return hits >= min(1, len(missing))


def _mentions_limitations(text: str, limitations: list[str]) -> bool:
    if "limitation" in text or "do not claim" in text:
        return True
    for item in limitations:
        snippet = " ".join(str(item).lower().split()[:4])
        if snippet and snippet in text:
            return True
    return False
