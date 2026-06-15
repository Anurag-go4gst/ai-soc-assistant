"""Phase 3 — advisory MITRE + severity rationale prose from fixed decision dumps only."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.prompts import PROMPT_CONTRACTS
from app.llm.sidecar_clients import invoke_sidecar_role
from app.llm.sidecar_skip_policy import should_skip_sidecar
from app.risk.severity_policy import SeverityDecision
from app.synthesis import claim_patterns

MITRE_REASONER_ROLE = "mitre_reasoner"
RISK_RATIONALE_ROLE = "risk_rationale_reasoner"

_NEGATION = claim_patterns.NEGATION
_EXECUTED_SPL = claim_patterns.EXECUTED_SPL
_COMPROMISE = claim_patterns.COMPROMISE
_EVIDENCE_SUPPORTED = claim_patterns.EVIDENCE_SUPPORTED
_SEVERITY_TOKEN = claim_patterns.SEVERITY_TOKEN


@dataclass(frozen=True)
class MitreRiskRationaleResult:
    severity_rationale_prose: str | None = None
    mitre_rationale_prose: str | None = None
    llm_called: bool = False
    guard_status: str = "skipped"
    fallback_used: bool = False
    skipped_reason: str | None = None
    provider_label: str | None = None
    adapter_warnings: list[str] = field(default_factory=list)

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "llm_called": self.llm_called,
            "guard_status": self.guard_status,
            "fallback_used": self.fallback_used,
            "skipped_reason": self.skipped_reason,
            "provider_label": self.provider_label,
            "severity_rationale_present": bool(self.severity_rationale_prose),
            "mitre_rationale_present": bool(self.mitre_rationale_prose),
            "adapter_warnings": list(self.adapter_warnings),
        }


def mitre_risk_rationale_enabled() -> bool:
    return bool(
        settings.control_plane_enabled
        and settings.ai_soc_llm_final_synthesis_enabled
        and settings.ai_soc_llm_live_synthesis_enabled
    )


def build_deterministic_severity_rationale(severity_decision: SeverityDecision | None) -> str | None:
    if severity_decision is None:
        return None
    parts: list[str] = []
    if severity_decision.matched_rules:
        parts.append("Matched: " + "; ".join(str(item) for item in severity_decision.matched_rules if item))
    if severity_decision.why_not_higher:
        parts.append("Why not higher: " + "; ".join(str(item) for item in severity_decision.why_not_higher if item))
    if severity_decision.missing_evidence:
        parts.append(
            "Missing for escalation: " + "; ".join(str(item) for item in severity_decision.missing_evidence if item)
        )
    text = " ".join(parts).strip()
    return text or None


def build_deterministic_mitre_rationale(
    *,
    contract: AnswerContract,
    mitre_branch_result: dict[str, Any] | None,
) -> str | None:
    branch = mitre_branch_result if isinstance(mitre_branch_result, dict) else {}
    parts: list[str] = []
    if contract.candidate_mitre:
        parts.append(
            "Candidate MITRE (metadata only): "
            + ", ".join(str(item) for item in contract.candidate_mitre[:8])
        )
    if contract.evidence_supported_mitre:
        parts.append(
            "Evidence-supported MITRE: "
            + ", ".join(str(item) for item in contract.evidence_supported_mitre[:8])
        )
    if contract.not_claimed_mitre:
        parts.append(
            "Not claimed due to insufficient evidence: "
            + ", ".join(str(item) for item in contract.not_claimed_mitre[:8])
        )
    if branch.get("branch_authority"):
        parts.append(f"Branch authority: {branch.get('branch_authority')}")
    text = " ".join(parts).strip()
    return text or None


def validate_rationale_prose(
    text: str,
    *,
    severity_label: str | None,
    contract: AnswerContract,
) -> tuple[bool, str | None]:
    lowered = " ".join(text.split()).lower()
    if not lowered.strip():
        return False, "Rationale prose is empty."

    contract_severity = _severity_token(severity_label)
    prose_severities = {token.upper() for token in _SEVERITY_TOKEN.findall(text)}
    if contract_severity and prose_severities:
        for foreign in prose_severities - {contract_severity}:
            if claim_patterns.severity_token_is_upgrade_claim(text, foreign):
                return False, "Rationale prose introduces a severity level not in the decision dump."

    supported = {tid.upper() for tid in contract.evidence_supported_mitre}
    candidate = {tid.upper() for tid in contract.candidate_mitre}
    if not supported and _EVIDENCE_SUPPORTED.search(lowered) and not _NEGATION.search(lowered):
        return False, "Rationale uses evidence-supported wording without decision support."

    for tid in candidate:
        if tid.upper() not in supported and tid.lower() in lowered:
            if any(
                phrase in lowered
                for phrase in (
                    "not evidence-supported",
                    "not evidence supported",
                    "remains candidate",
                    "stay candidate",
                    "candidate only",
                )
            ):
                continue
            if _EVIDENCE_SUPPORTED.search(lowered):
                return False, f"Rationale upgrades candidate MITRE {tid} to evidence-supported."

    if _COMPROMISE.search(lowered) and "not claim" not in lowered and "do not claim" not in lowered:
        blocked = {str(item).lower() for item in contract.unsupported_claims_avoid}
        if "account_compromise" in blocked or "account compromis" in blocked:
            return False, "Rationale claims compromise without decision support."

    exec_label = str(contract.execution_status_label or "")
    if _EXECUTED_SPL.search(lowered) and exec_label not in {"executed_mock_evidence", "executed_live_evidence"}:
        return False, "Rationale claims SPL execution without decision support."

    return True, None


def run_mitre_risk_rationale(
    *,
    contract: AnswerContract,
    query: str,
    severity_decision: SeverityDecision | None,
    mitre_decision: dict[str, Any] | None,
    mitre_branch_result: dict[str, Any] | None,
    budget_exhausted: bool = False,
    budget: Any = None,
) -> MitreRiskRationaleResult:
    """Advisory rationale prose. ``budget`` (a ``TurnLlmBudget``) is checked and
    recorded **per internal sidecar call** so the two reasoning roles cannot exceed
    the per-turn cap — each call counts as one sidecar, not the pair as one."""
    det_severity = build_deterministic_severity_rationale(severity_decision)
    det_mitre = build_deterministic_mitre_rationale(
        contract=contract,
        mitre_branch_result=mitre_branch_result,
    )

    if not mitre_risk_rationale_enabled():
        return MitreRiskRationaleResult(
            severity_rationale_prose=det_severity,
            mitre_rationale_prose=det_mitre,
            guard_status="disabled",
            fallback_used=True,
            skipped_reason="rationale_disabled",
        )
    if budget_exhausted:
        return MitreRiskRationaleResult(
            severity_rationale_prose=det_severity,
            mitre_rationale_prose=det_mitre,
            guard_status="skipped",
            fallback_used=True,
            skipped_reason="turn_budget_exhausted",
        )

    skip, skip_reason = should_skip_sidecar(
        answer_mode=contract.answer_mode,
        hil_status=contract.hil_status,
    )
    if skip:
        return MitreRiskRationaleResult(
            severity_rationale_prose=det_severity,
            mitre_rationale_prose=det_mitre,
            guard_status="skipped",
            fallback_used=True,
            skipped_reason=skip_reason,
        )

    decision_dump = _build_decision_dump(
        contract=contract,
        severity_decision=severity_decision,
        mitre_decision=mitre_decision,
        mitre_branch_result=mitre_branch_result,
    )
    deterministic_context = {
        "severity_label": severity_decision.severity_label if severity_decision else contract.severity_label,
        "candidate_mitre": list(contract.candidate_mitre),
        "evidence_supported_mitre": list(contract.evidence_supported_mitre),
        "not_claimed_mitre": list(contract.not_claimed_mitre),
    }

    llm_called = False
    provider_label: str | None = None
    warnings: list[str] = []
    severity_prose = det_severity
    mitre_prose = det_mitre
    guard_status = "passed"
    fallback_used = False

    def _budget_blocks() -> bool:
        return budget is not None and budget.sidecar_budget_exhausted()

    if (det_mitre or contract.candidate_mitre or contract.mitre_technique_ids) and not _budget_blocks():
        mitre_prose, called, label, role_warnings, blocked = _invoke_reasoning_role(
            role=MITRE_REASONER_ROLE,
            query=query,
            decision_dump=decision_dump,
            deterministic_context=deterministic_context,
            fallback_prose=det_mitre,
            severity_label=severity_decision.severity_label if severity_decision else contract.severity_label,
            contract=contract,
        )
        llm_called = llm_called or called
        provider_label = provider_label or label
        warnings.extend(role_warnings)
        if called and budget is not None:
            budget.record_sidecar(role=MITRE_REASONER_ROLE, provider_label=label, outcome="completed")
        if blocked:
            guard_status = "blocked"
            fallback_used = True
            mitre_prose = det_mitre

    if severity_decision and severity_decision.severity_label and not _budget_blocks():
        severity_prose, called, label, role_warnings, blocked = _invoke_reasoning_role(
            role=RISK_RATIONALE_ROLE,
            query=query,
            decision_dump=decision_dump,
            deterministic_context=deterministic_context,
            fallback_prose=det_severity,
            severity_label=severity_decision.severity_label,
            contract=contract,
        )
        llm_called = llm_called or called
        provider_label = provider_label or label
        warnings.extend(role_warnings)
        if called and budget is not None:
            budget.record_sidecar(role=RISK_RATIONALE_ROLE, provider_label=label, outcome="completed")
        if blocked:
            guard_status = "blocked"
            fallback_used = True
            severity_prose = det_severity

    if not llm_called:
        guard_status = "skipped"
        fallback_used = True

    return MitreRiskRationaleResult(
        severity_rationale_prose=severity_prose,
        mitre_rationale_prose=mitre_prose,
        llm_called=llm_called,
        guard_status=guard_status,
        fallback_used=fallback_used,
        provider_label=provider_label,
        adapter_warnings=warnings,
    )


def _invoke_reasoning_role(
    *,
    role: str,
    query: str,
    decision_dump: dict[str, Any],
    deterministic_context: dict[str, Any],
    fallback_prose: str | None,
    severity_label: str | None,
    contract: AnswerContract,
) -> tuple[str | None, bool, str | None, list[str], bool]:
    contract_text = PROMPT_CONTRACTS.get(role) or PROMPT_CONTRACTS["pattern_reasoner"]
    system = str(contract_text.get("system_instruction") or "")
    user_prompt = (
        "Explain the fixed MITRE/severity decision dump below in 2-4 review-only sentences. "
        "Return JSON matching the role schema. Never change severity, MITRE status, or execution.\n"
        f"QUESTION: {query}\n"
        f"DECISION DUMP:\n{json.dumps(decision_dump, ensure_ascii=False)}"
    )
    raw, timed_out, provider_label = invoke_sidecar_role(
        role=role,
        user_prompt=user_prompt,
        system_prompt=system,
        max_tokens=500,
    )
    if timed_out or not raw:
        return fallback_prose, bool(timed_out or raw is not None), provider_label, [], False

    adapted = adapt_llm_output(
        role=role,
        raw_output=raw,
        deterministic_context=deterministic_context,
    )
    warnings = list(adapted.warnings + adapted.errors)
    if adapted.accepted and isinstance(adapted.normalized_payload, dict):
        prose = _prose_from_payload(role, adapted.normalized_payload)
    else:
        extraction = extract_first_json_object(raw)
        if extraction.parsed_ok and isinstance(extraction.payload, dict):
            prose = _prose_from_payload(role, extraction.payload)
            warnings.extend(extraction.warnings + extraction.errors)
        else:
            return fallback_prose, True, provider_label, warnings, False

    passed, reason = validate_rationale_prose(
        prose,
        severity_label=severity_label,
        contract=contract,
    )
    if not passed:
        return fallback_prose, True, provider_label, warnings + ([reason] if reason else []), True
    return prose, True, provider_label, warnings, False


def _prose_from_payload(role: str, payload: dict[str, Any]) -> str:
    if role == RISK_RATIONALE_ROLE:
        chunks: list[str] = []
        for key in ("why_selected", "why_not_higher", "missing_evidence_for_higher", "escalate_if"):
            for item in payload.get(key) or []:
                if item:
                    chunks.append(str(item))
        if payload.get("recommended_validation_steps"):
            chunks.extend(str(item) for item in payload["recommended_validation_steps"] if item)
        return " ".join(chunks).strip()

    chunks = []
    if payload.get("reasoning_summary"):
        chunks.append(str(payload["reasoning_summary"]))
    if payload.get("pattern_characterization"):
        chunks.append(str(payload["pattern_characterization"]))
    for item in payload.get("mitre_reasoning") or []:
        if isinstance(item, str):
            chunks.append(item)
        elif isinstance(item, dict):
            tid = str(item.get("technique_id") or "")
            reason = str(item.get("reasoning") or item.get("reason") or "")
            if tid or reason:
                chunks.append(f"{tid}: {reason}".strip(": "))
    for item in payload.get("why_not_higher_or_final") or []:
        if item:
            chunks.append(str(item))
    return " ".join(chunks).strip()


def _build_decision_dump(
    *,
    contract: AnswerContract,
    severity_decision: SeverityDecision | None,
    mitre_decision: dict[str, Any] | None,
    mitre_branch_result: dict[str, Any] | None,
) -> dict[str, Any]:
    severity_payload = None
    if severity_decision is not None:
        severity_payload = severity_decision.model_dump()
    return {
        "severity": severity_payload,
        "mitre_decision": mitre_decision or {},
        "mitre_branch_result": mitre_branch_result or {},
        "contract_mitre": {
            "candidate_mitre": list(contract.candidate_mitre),
            "evidence_supported_mitre": list(contract.evidence_supported_mitre),
            "requires_validation_mitre": list(contract.requires_validation_mitre),
            "not_claimed_mitre": list(contract.not_claimed_mitre),
            "ruled_out_mitre": list(contract.ruled_out_mitre),
        },
        "missing_evidence": list(contract.missing_evidence),
        "limitations": list(contract.limitations),
        "execution_status_label": contract.execution_status_label,
        "spl_status": contract.spl_status,
    }


def _severity_token(label: str | None) -> str | None:
    if not label:
        return None
    match = _SEVERITY_TOKEN.search(label)
    return match.group(0).upper() if match else None
