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
from app.llm.governed_context_package import GovernedContextPackage
from app.synthesis import claim_patterns
from app.synthesis.composition_confidence import qualifies_for_weak_case_composition
from app.chat.final_answer_readability import apply_draft_preview_readability
from app.config import settings
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.schemas.responses import AnalystResponseEnvelope
from app.threat.mitre_permitted_builder import canonical_technique_name_tactic

# Tuned for an on-prem 8B instruct (Foundation-Sec): short, numbered, front-loaded
# critical rules with a closing self-check. The model loses constraints buried in
# long prose, so the five things the grounding/notice/MITRE guards enforce are
# stated first and repeated at the end.
_SYSTEM_PROMPT = (
    "You are a SOC analyst assistant. You receive a GOVERNED ANSWER CONTRACT of "
    "facts already decided by the security pipeline. Restate ONLY those facts in "
    "2-4 short, plain sentences.\n\n"
    "CRITICAL RULES (these override everything else):\n"
    "1. If the contract has a REQUIRED NOTICE line, copy that exact sentence into "
    "your answer, word for word.\n"
    "2. Only write MITRE technique IDs that the contract lists as allowed. Never "
    "introduce any other T#### id or technique name. If none are allowed, write no "
    "technique id at all.\n"
    "3. Candidate MITRE stays candidate. Never write 'evidence-supported' unless "
    "the contract's evidence-supported list contains that exact id.\n"
    "4. Never say SPL was approved or executed, that Splunk/MCP returned rows or "
    "live results, or that compromise is confirmed — unless the contract execution "
    "status literally says executed.\n"
    "5. Never invent a severity level, index, sourcetype, source IP, hostname, "
    "hash, or SPL query. Use only values present in the contract/context.\n\n"
    "ALSO:\n"
    "- Keep every missing-evidence and limitation caveat from the contract.\n"
    "- If human review is required, say review is required.\n"
    "- Not-claimed MITRE = insufficient supporting evidence (do NOT say 'ruled out').\n"
    "- Use MITRE technique names exactly as listed.\n"
    "- If SPL template_status is active but the source profile is missing, say the "
    "governed SPL template is active but generation is blocked/review-required until "
    "required fields are confirmed; never say no active template exists.\n"
    "- Use only the provided context. If a snippet, skill, or tool hint is "
    "irrelevant or your confidence is low, ignore it and say what is missing rather "
    "than inventing anything.\n"
    "- No SPL queries, no tool instructions, no GitHub references. Plain prose only.\n\n"
    "BEFORE YOU FINISH, CHECK: REQUIRED NOTICE copied verbatim? Only allowed "
    "technique IDs used? No new severity, execution, or compromise claim?"
)

# Shared claim patterns live in app.synthesis.claim_patterns (leaf module) so
# the Tier-D quality checks can reuse them without importing this module's
# pipeline-coupled import chain. Aliases keep composer internals unchanged.
_GITHUB_MARKERS = claim_patterns.GITHUB_MARKERS
_EXECUTED_SPL = claim_patterns.EXECUTED_SPL
_APPROVED_EXEC = claim_patterns.APPROVED_EXEC
_COMPROMISE = claim_patterns.COMPROMISE
_NEGATION = claim_patterns.NEGATION
_EVIDENCE_SUPPORTED = claim_patterns.EVIDENCE_SUPPORTED
_SUPPORTING_EVIDENCE_CONTEXT = re.compile(
    r"\b("
    r"supporting evidence|"
    r"evidence[- ]supported|"
    r"evidence supported|"
    r"confirmed technique|"
    r"identified with supporting evidence|"
    r"with supporting evidence"
    r")\b",
    re.IGNORECASE,
)
_MITRE_TECHNIQUE_ID = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
_MITRE_NAME_IN_PROSE = re.compile(
    r"\b(T\d{4}(?:\.\d{3})?)\b\s*(?:\(([^)]+)\)|[-–:]\s*([A-Za-z][A-Za-z0-9 /-]{2,}))",
    re.IGNORECASE,
)
_MISSING_EVIDENCE_LIST = re.compile(
    r"missing evidence includes\s+([^.;\n]+)",
    re.IGNORECASE,
)
_SEVERITY_TOKEN = re.compile(r"\bP[1-4]\b", re.IGNORECASE)


@dataclass(frozen=True)
class GovernedComposerResult:
    envelope: AnalystResponseEnvelope
    llm_composer_enabled: bool
    llm_composer_used: bool
    llm_guard_status: str
    llm_fallback_used: bool
    llm_blocked_reason: str | None = None
    llm_provider_label: str | None = None
    llm_raw_output_redacted: str | None = None

    def trace_payload(self) -> dict[str, Any]:
        attempted = self.llm_composer_enabled and self.llm_guard_status in {
            "passed",
            "blocked",
            "pending",
        }
        payload = {
            "llm_composer_enabled": self.llm_composer_enabled,
            "llm_composer_used": self.llm_composer_used,
            "llm_guard_status": self.llm_guard_status,
            "llm_fallback_used": self.llm_fallback_used,
            "llm_blocked_reason": self.llm_blocked_reason,
            "composer_attempted": attempted or self.llm_composer_used,
        }
        if self.llm_provider_label:
            payload["llm_provider_label"] = self.llm_provider_label
            payload["llm_answered_label"] = self.llm_provider_label
        if self.llm_raw_output_redacted:
            payload["llm_raw_output_placeholder"] = self.llm_raw_output_redacted[:500]
        return payload


def composer_is_enabled() -> bool:
    return (
        settings.control_plane_enabled
        and settings.ai_soc_llm_final_synthesis_enabled
        and settings.ai_soc_llm_live_synthesis_enabled
    )


def build_composer_runtime_status() -> dict[str, Any]:
    """Redacted runtime/config snapshot for trace/UI diagnosis (no secrets)."""
    mode = settings.ai_soc_llm_mode.strip().lower()
    base_url_configured = bool(
        (settings.ai_soc_llm_local_base_url if mode == "local" else settings.ai_soc_llm_openai_base_url).strip()
    )
    model_configured = bool(
        (
            settings.ai_soc_llm_local_model
            if mode == "local"
            else settings.ai_soc_llm_openai_model
        ).strip()
        or settings.ai_soc_llm_default_model.strip()
    )
    provider_configured = build_synthesis_client_from_settings() is not None
    enabled = composer_is_enabled()
    return {
        "control_plane_enabled": settings.control_plane_enabled,
        "ai_soc_llm_final_synthesis_enabled": settings.ai_soc_llm_final_synthesis_enabled,
        "ai_soc_llm_live_synthesis_enabled": settings.ai_soc_llm_live_synthesis_enabled,
        "ai_soc_llm_mode": mode or "unset",
        "ai_soc_llm_answer_guard_enabled": settings.ai_soc_llm_answer_guard_enabled,
        "composer_is_enabled": enabled,
        "provider_configured": provider_configured,
        "provider_url_configured": base_url_configured,
        "provider_model_configured": model_configured,
        "provider_skip_reason": None if provider_configured else "no_provider_configured",
        "composer_attempted": False,
        "llm_composer_enabled": enabled,
        "llm_composer_used": False,
        "llm_guard_status": "disabled" if not enabled else "pending",
        "llm_fallback_used": False,
        "expected_latency_hint": (
            "On-prem single-slot model: live narration can take ~60s; the wait is "
            "expected. Facts stay deterministic and fall back if the model is slow."
        )
        if enabled
        else None,
    }


def build_composer_prompt(
    contract: AnswerContract,
    enrichment_projection: dict[str, Any] | None,
    *,
    context_package: GovernedContextPackage | None = None,
    weak_case_composition: bool = False,
) -> str:
    """Build a contract-only composer prompt (no raw events or GitHub content)."""
    projection = enrichment_projection or {}
    knowledge_profile = _is_knowledge_profile(contract)
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
    # Front-load the required out-of-catalog notice so the model can copy it (the 8B
    # cannot echo a sentence it was never given — this was the top guard-block cause).
    notice = str(getattr(contract, "out_of_catalog_notice", "") or "").strip()
    if notice:
        lines.append(f'- REQUIRED NOTICE — copy this sentence verbatim into your answer: "{notice}"')
    if knowledge_profile and not weak_case_composition:
        lines.append("- Answer mode: governed SOP / knowledge recall.")
        if checklist:
            lines.append("- Analyst checklist: " + "; ".join(checklist))
        if answer_rules:
            lines.append("- Answer rules: " + "; ".join(answer_rules))
        lines.append("\nWrite the analyst summary now using only the contract facts above.")
        return "\n".join(lines)

    if contract.severity_label:
        lines.append(f"- Severity (deterministic): {contract.severity_label}")
    lines.append(f"- SPL status: {contract.spl_status}")
    if contract.spl_status_detail:
        detail = contract.spl_status_detail
        lines.append(
            "- SPL display status: "
            f"template_status={detail.get('template_status')}; "
            f"generation_status={detail.get('generation_status')}; "
            f"review_required={detail.get('review_required')}; "
            f"block_reason={detail.get('block_reason')}; "
            f"required_fields={', '.join(str(item) for item in detail.get('required_fields') or [])}"
        )
        if (
            detail.get("template_status") == "active"
            and detail.get("block_reason") == "spl_template_active_source_profile_missing"
        ):
            lines.append(
                "- SPL wording: governed SPL template is active, but source profile is missing, "
                "so SPL generation is blocked/review-required until required fields are confirmed."
            )
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

    _append_mitre_bucket(
        lines,
        "Candidate MITRE (metadata only; never evidence-supported)",
        contract.candidate_mitre,
    )
    _append_mitre_bucket(
        lines,
        "Evidence-supported MITRE (only these may be called evidence-supported)",
        contract.evidence_supported_mitre,
    )
    _append_mitre_bucket(lines, "Requires validation MITRE", contract.requires_validation_mitre)
    _append_mitre_bucket(
        lines,
        "Not claimed MITRE (insufficient supporting evidence)",
        contract.not_claimed_mitre,
    )
    _append_mitre_bucket(lines, "Ruled out MITRE", contract.ruled_out_mitre)
    name_lines = _contract_mitre_name_lines(contract)
    if name_lines:
        lines.append("- Authoritative MITRE names (use exactly; do not rename):")
        lines.extend(name_lines)
    if contract.mitre_technique_ids:
        lines.append("- Visible MITRE technique IDs: " + ", ".join(contract.mitre_technique_ids))
    # Explicit allow-list so the 8B does not introduce an unlisted technique id
    # (the second top guard-block cause).
    allowed_ids = sorted(_contract_mitre_ids(contract))
    if allowed_ids:
        lines.append(
            "- ALLOWED MITRE technique IDs (the ONLY ids you may write): "
            + ", ".join(allowed_ids)
            + ". Do not write any other T#### id."
        )
    else:
        lines.append("- No MITRE technique is in scope — do NOT write any T#### id.")

    if contract.human_review_required or contract.hil_status in {
        "required",
        "clarification_required",
        "missing_evidence_review",
    }:
        lines.append("- Human review: required before any execution or destructive action.")

    if contract.out_of_catalog_notice:
        lines.append(
            "- Out-of-catalog notice (must preserve in prose): "
            + str(contract.out_of_catalog_notice)
        )
    if contract.investigation_steps:
        lines.append("- Investigation steps: " + "; ".join(contract.investigation_steps[:6]))
    if contract.nearest_questions:
        nearest = [
            str(item.get("question_ref") or item.get("label") or "")
            for item in contract.nearest_questions[:3]
            if isinstance(item, dict)
        ]
        nearest = [item for item in nearest if item]
        if nearest:
            lines.append("- Nearest catalog questions (suggestions only): " + ", ".join(nearest))

    if context_package is not None and weak_case_composition:
        lines.append(
            "\nGOVERNED CONTEXT (cite-only; ignore irrelevant snippets; declare gaps instead of inventing):"
        )
        lines.append(context_package.to_prompt_block())

    lines.append("\nWrite the analyst summary now using only the contract facts above.")
    return "\n".join(lines)


# Phase 2.5 grounding guard — high-signal fabrication patterns. Low false-positive
# by design: only source/IOC/SPL tokens are checked, not generic prose words.
_IOC_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IOC_HASH = re.compile(r"\b[a-fA-F0-9]{32,64}\b")
_SPL_SOURCE = re.compile(r"\b(?:index|sourcetype|source)\s*=\s*([A-Za-z0-9_\-:*]+)", re.IGNORECASE)
_SPL_PIPE_CMD = re.compile(r"\|\s*(stats|tstats|eval|where|table|rex|timechart|dedup|lookup|search)\b", re.IGNORECASE)


def validate_grounding(text: str, allowed_corpus: str) -> tuple[bool, str | None]:
    """Cite-only-retrieved guard (Phase 2.5).

    Reject prose that introduces source/IOC/SPL tokens not present in the governed
    context corpus (prompt + contract facts). This is what makes LLM composition on
    out-of-catalog / weak cases safe: the model may narrate and propose, never invent
    a concrete index, source IP, hash, or runnable SPL the pipeline did not provide.
    """
    corpus = allowed_corpus.lower()

    for ip in _IOC_IPV4.findall(text):
        if ip.lower() not in corpus:
            return False, f"Composed prose introduces source/IOC IP '{ip}' not in governed context."
    for digest in _IOC_HASH.findall(text):
        if digest.lower() not in corpus:
            return False, f"Composed prose introduces hash '{digest[:12]}…' not in governed context."
    for source_value in _SPL_SOURCE.findall(text):
        if source_value.lower() not in corpus:
            return False, f"Composed prose names a source '{source_value}' not in governed context."
    pipe_cmd = _SPL_PIPE_CMD.search(text)
    if pipe_cmd and pipe_cmd.group(0).lower() not in corpus:
        return False, "Composed prose contains a runnable SPL pipeline not provided by the pipeline."
    return True, None


def out_of_catalog_notice_preserved(text: str, contract: AnswerContract) -> tuple[bool, str | None]:
    """When the contract carries an out-of-catalog notice, the body must keep it."""
    notice = str(getattr(contract, "out_of_catalog_notice", "") or "").strip()
    if not notice:
        return True, None
    lowered = text.lower()
    if "out-of-catalog" in lowered or "out of catalog" in lowered or "not a vetted" in lowered:
        return True, None
    if "validate against" in lowered and ("local telemetry" in lowered or "policy" in lowered):
        return True, None
    return False, "Composed prose dropped the required out-of-catalog notice."


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

    for tid in candidate:
        if tid.upper() not in supported and _technique_claims_evidence_supported(lowered, tid):
            return False, f"Candidate MITRE {tid} was upgraded to evidence-supported in prose."

    for tid in _MITRE_TECHNIQUE_ID.findall(text):
        tid_upper = tid.upper()
        if tid_upper not in supported and _technique_claims_evidence_supported(lowered, tid):
            return False, f"MITRE {tid_upper} described as evidence-supported without contract support."

    name_mismatch = _mitre_name_mismatch(text, contract)
    if name_mismatch:
        return False, name_mismatch

    extraneous_missing = _extraneous_missing_evidence_mention(text, contract)
    if extraneous_missing:
        return False, extraneous_missing

    # A knowledge / MITRE-explanation answer legitimately discusses the technique it
    # was asked about (e.g. "what does T1110 cover"), even when that id is not in the
    # contract's evidence buckets. The evidence-supported / executed / compromise
    # guards above still apply, so the technique can be named but never claimed.
    if not _is_knowledge_profile(contract):
        for tid in _MITRE_TECHNIQUE_ID.findall(text):
            if tid.upper() not in allowed_techniques and tid.upper() not in {
                x.upper() for x in contract.not_claimed_mitre
            } | {x.upper() for x in contract.ruled_out_mitre}:
                return False, f"Composed prose introduces unsupported MITRE technique {tid.upper()}."

    if _COMPROMISE.search(lowered) and not _NEGATION.search(lowered):
        blocked_claims = {str(item).lower() for item in contract.unsupported_claims_avoid}
        if "account_compromise" in blocked_claims or "account compromis" in blocked_claims:
            return False, "Composed prose claims compromise without contract support."

    if not supported and _EVIDENCE_SUPPORTED.search(lowered):
        return False, "Composed prose uses evidence-supported wording without contract support."

    exec_label = str(contract.execution_status_label or "")
    if _EXECUTED_SPL.search(lowered) and exec_label not in {"executed_mock_evidence", "executed_live_evidence"}:
        return False, "Composed prose claims SPL execution without contract support."

    if _APPROVED_EXEC.search(lowered):
        return False, "Composed prose claims SPL approval or execution eligibility."

    if _active_template_source_profile_missing(contract) and "no active governed spl template" in lowered:
        return False, "Composed prose contradicts active SPL template status."

    if _active_template_source_profile_missing(contract):
        if "template" in lowered and "active" not in lowered:
            return False, "Composed prose omitted active SPL template status."

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

    for tid in contract.not_claimed_mitre:
        if _technique_uses_ruled_out_wording(lowered, tid):
            return False, f"Not-claimed MITRE {tid} was described as ruled out."

    if contract.not_claimed_mitre:
        if "not claimed" in lowered and "insufficient" not in lowered and "supporting evidence" not in lowered:
            return False, "Composed prose omitted insufficient-evidence wording for not-claimed MITRE."

    return True, None


def compose_governed_answer(
    *,
    contract: AnswerContract,
    enrichment_projection: dict[str, Any] | None,
    fallback_envelope: AnalystResponseEnvelope,
    client: LocalChatClient | None = None,
    context_package: GovernedContextPackage | None = None,
    path_type: str | None = None,
    intent_family: str | None = None,
) -> GovernedComposerResult:
    """Compose governed prose or return the Phase 8 deterministic envelope."""
    if fallback_envelope.draft_spl_code:
        return GovernedComposerResult(
            envelope=apply_draft_preview_readability(fallback_envelope),
            llm_composer_enabled=composer_is_enabled(),
            llm_composer_used=False,
            llm_guard_status="skipped",
            llm_fallback_used=False,
            llm_blocked_reason="draft_spl_preview_active",
        )
    if not composer_is_enabled():
        return GovernedComposerResult(
            envelope=fallback_envelope,
            llm_composer_enabled=False,
            llm_composer_used=False,
            llm_guard_status="disabled",
            llm_fallback_used=False,
        )
    weak_case = qualifies_for_weak_case_composition(
        contract,
        path_type=path_type,
        intent_family=intent_family,
    )
    if _is_knowledge_profile(contract) and not weak_case:
        return GovernedComposerResult(
            envelope=fallback_envelope,
            llm_composer_enabled=True,
            llm_composer_used=False,
            llm_guard_status="skipped",
            llm_fallback_used=False,
            llm_blocked_reason="Knowledge/SOP profile uses deterministic governed RAG summary.",
        )

    prompt = build_composer_prompt(
        contract,
        enrichment_projection,
        context_package=context_package,
        weak_case_composition=weak_case,
    )
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
            llm_guard_status="blocked",
            llm_fallback_used=True,
            llm_blocked_reason=exc.user_message,
        )

    composed = result.text.strip()
    passed, blocked_reason = validate_composed_prose(composed, contract)
    if passed:
        # Phase 2.5: cite-only grounding + out-of-catalog notice (corpus = prompt + facts).
        passed, blocked_reason = validate_grounding(composed, prompt + "\n" + str(contract.model_dump()))
    if passed:
        passed, blocked_reason = out_of_catalog_notice_preserved(composed, contract)
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
    provider_label = result.answered_label or None
    if not provider_label:
        chain = getattr(llm_client, "chain", None)
        if chain:
            provider_label = chain[0][0]
    return GovernedComposerResult(
        envelope=AnalystResponseEnvelope.model_validate(payload),
        llm_composer_enabled=True,
        llm_composer_used=True,
        llm_guard_status="passed",
        llm_fallback_used=False,
        llm_provider_label=provider_label,
        llm_raw_output_redacted=composed[:500],
    )


def _is_knowledge_profile(contract: AnswerContract) -> bool:
    return contract.answer_mode == "rag_only" or contract.intent_family in {
        "sop_or_playbook",
        "policy_knowledge",
        "knowledge_only",
    }


def _append_mitre_bucket(lines: list[str], label: str, values: list[str]) -> None:
    if values:
        rendered = []
        for tid in values:
            canonical = canonical_technique_name_tactic(tid)
            if canonical:
                rendered.append(f"{tid} ({canonical[0]})")
            else:
                rendered.append(tid)
        lines.append(f"- {label}: " + ", ".join(rendered))


def _contract_mitre_ids(contract: AnswerContract) -> set[str]:
    buckets = (
        contract.candidate_mitre,
        contract.evidence_supported_mitre,
        contract.requires_validation_mitre,
        contract.not_claimed_mitre,
        contract.ruled_out_mitre,
        contract.mitre_technique_ids,
    )
    return {tid.upper() for bucket in buckets for tid in bucket if tid}


def _contract_mitre_name_lines(contract: AnswerContract) -> list[str]:
    lines: list[str] = []
    for tid in sorted(_contract_mitre_ids(contract)):
        canonical = canonical_technique_name_tactic(tid)
        if canonical:
            lines.append(f"  - {tid}: {canonical[0]}")
    return lines


def _technique_claims_evidence_supported(text: str, technique_id: str) -> bool:
    tid = technique_id.lower()
    if tid not in text:
        return False
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        sentence_l = sentence.lower()
        if tid not in sentence_l:
            continue
        if any(
            phrase in sentence_l
            for phrase in (
                "not claimed",
                "remains candidate",
                "stay candidate",
                "stays candidate",
                "candidate only",
                "requires validation",
            )
        ):
            continue
        if _SUPPORTING_EVIDENCE_CONTEXT.search(sentence_l) or _EVIDENCE_SUPPORTED.search(sentence_l):
            return True
    window = text[max(0, text.index(tid) - 120) : text.index(tid) + 120]
    if any(
        phrase in window
        for phrase in ("not claimed", "remains candidate", "stay candidate", "stays candidate")
    ):
        return False
    return bool(_SUPPORTING_EVIDENCE_CONTEXT.search(window) or _EVIDENCE_SUPPORTED.search(window))


def _mitre_name_mismatch(text: str, contract: AnswerContract) -> str | None:
    for match in _MITRE_NAME_IN_PROSE.finditer(text):
        tid = match.group(1).upper()
        stated_name = (match.group(2) or match.group(3) or "").strip()
        if not stated_name or tid not in _contract_mitre_ids(contract):
            continue
        canonical = canonical_technique_name_tactic(tid)
        if canonical is None:
            continue
        if stated_name.lower() != canonical[0].lower():
            return (
                f"MITRE {tid} name '{stated_name}' does not match contract name '{canonical[0]}'."
            )
    return None


def _extraneous_missing_evidence_mention(text: str, contract: AnswerContract) -> str | None:
    allowed = {str(item).lower() for item in contract.missing_evidence}
    allowed_tokens: set[str] = set()
    for item in allowed:
        allowed_tokens.update(part for part in re.split(r"[_\s]+", item) if len(part) >= 3)
    for limitation in contract.limitations:
        allowed_tokens.update(
            part for part in re.split(r"[_\s\-]+", str(limitation).lower()) if len(part) >= 4
        )

    for match in _MISSING_EVIDENCE_LIST.finditer(text):
        chunk = match.group(1).lower()
        for marker, aliases in _MISSING_EVIDENCE_MARKERS.items():
            if not any(alias in chunk for alias in aliases):
                continue
            if marker in allowed:
                continue
            if any(alias in allowed_tokens for alias in aliases):
                continue
            return (
                f"Composed prose mentions missing evidence '{marker}' not present in contract."
            )
    return None


_MISSING_EVIDENCE_MARKERS: dict[str, tuple[str, ...]] = {
    "mfa_status": ("mfa_status", "mfa status", "mfa result"),
    "post_login_activity": ("post_login_activity", "post-login activity", "post login activity"),
    "privileged_account_impacted": ("privilege status", "privileged account"),
    "critical_asset": ("asset criticality", "critical asset"),
    "source_ownership": ("source ip ownership", "source ownership"),
    "confirmed_success": ("confirmed success", "successful login confirmation"),
}


def _technique_uses_ruled_out_wording(text: str, technique_id: str) -> bool:
    tid = technique_id.lower()
    if tid not in text:
        return False
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if tid in sentence and "ruled out" in sentence:
            return True
    return False


def _active_template_source_profile_missing(contract: AnswerContract) -> bool:
    detail = contract.spl_status_detail or {}
    return (
        detail.get("template_status") == "active"
        and detail.get("block_reason") == "spl_template_active_source_profile_missing"
    )


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
