"""Advisory missing-evidence reasoning (non-authoritative prose bullets)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.governed_context_package import build_governed_context_package_for_contract
from app.llm.prompts import PROMPT_CONTRACTS
from app.llm.sidecar_clients import MISSING_EVIDENCE_ROLE, invoke_sidecar_role
from app.llm.sidecar_skip_policy import should_skip_sidecar

MISSING_EVIDENCE_ROLE_ID = MISSING_EVIDENCE_ROLE


@dataclass(frozen=True)
class MissingEvidenceReasonerResult:
    bullets: list[str] = field(default_factory=list)
    llm_called: bool = False
    timed_out: bool = False
    skipped_reason: str | None = None
    provider_label: str | None = None
    adapter_warnings: list[str] = field(default_factory=list)

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "llm_called": self.llm_called,
            "timed_out": self.timed_out,
            "skipped_reason": self.skipped_reason,
            "provider_label": self.provider_label,
            "bullet_count": len(self.bullets),
            "adapter_warnings": list(self.adapter_warnings),
        }


def run_missing_evidence_reasoner(
    *,
    contract: AnswerContract,
    query: str = "",
    soc_kb_snippets: list[str] | None = None,
    resource_decisions: list[str] | None = None,
) -> MissingEvidenceReasonerResult:
    if not settings.ai_soc_llm_enabled or settings.ai_soc_llm_mode.strip().lower() == "disabled":
        return MissingEvidenceReasonerResult(skipped_reason="llm_disabled")
    if not contract.missing_evidence:
        return MissingEvidenceReasonerResult(skipped_reason="no_missing_evidence_context")

    skip, skip_reason = should_skip_sidecar(
        answer_mode=contract.answer_mode,
        hil_status=contract.hil_status,
    )
    if skip:
        return MissingEvidenceReasonerResult(skipped_reason=skip_reason)

    context = build_governed_context_package_for_contract(
        query=query,
        contract=contract,
        soc_kb_snippets=soc_kb_snippets,
        resource_decisions=resource_decisions,
    )
    contract_text = PROMPT_CONTRACTS.get(MISSING_EVIDENCE_ROLE_ID) or {}
    system = str(contract_text.get("system_instruction") or PROMPT_CONTRACTS["pattern_reasoner"]["system_instruction"])
    user_prompt = (
        "Analyze missing evidence only. Return JSON with missing_evidence_analysis as "
        "a list of short review-only bullets citing what would strengthen the conclusion. "
        "Use only the governed context below; never invent evidence.\n"
        f"GOVERNED CONTEXT:\n{context.to_prompt_block()}"
    )

    raw, timed_out, provider_label = invoke_sidecar_role(
        role=MISSING_EVIDENCE_ROLE_ID,
        user_prompt=user_prompt,
        system_prompt=system,
        max_tokens=600,
    )
    if timed_out:
        return MissingEvidenceReasonerResult(
            llm_called=True,
            timed_out=True,
            provider_label=provider_label,
            skipped_reason="llm_timed_out",
        )
    if not raw:
        return MissingEvidenceReasonerResult(
            skipped_reason="no_provider_or_empty_output",
            provider_label=provider_label,
        )

    extraction = extract_first_json_object(raw)
    if not extraction.parsed_ok or extraction.payload is None:
        adapted = adapt_llm_output(role=MISSING_EVIDENCE_ROLE_ID, raw_output=raw)
        if adapted.ok and isinstance(adapted.payload, dict):
            bullets = _normalize_bullets(adapted.payload.get("missing_evidence_analysis"))
            return MissingEvidenceReasonerResult(
                bullets=bullets,
                llm_called=True,
                provider_label=provider_label,
                adapter_warnings=list(adapted.warnings),
            )
        return MissingEvidenceReasonerResult(
            llm_called=True,
            provider_label=provider_label,
            skipped_reason="json_extraction_failed",
            adapter_warnings=list(extraction.warnings + extraction.errors),
        )

    adapted = adapt_llm_output(role=MISSING_EVIDENCE_ROLE_ID, raw_output=raw)
    if not adapted.ok or not isinstance(adapted.payload, dict):
        return MissingEvidenceReasonerResult(
            llm_called=True,
            provider_label=provider_label,
            skipped_reason="adapter_rejected",
            adapter_warnings=list(adapted.warnings + adapted.errors),
        )
    bullets = _normalize_bullets(adapted.payload.get("missing_evidence_analysis"))
    return MissingEvidenceReasonerResult(
        bullets=bullets,
        llm_called=True,
        provider_label=provider_label,
        adapter_warnings=list(adapted.warnings),
    )


def _normalize_bullets(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:6]
