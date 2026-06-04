"""Final-answer validator — deterministic fail-closed backstop.

The AnswerContract + builder are the primary enforcer; a blocked finding shown
as a positive claim is a *builder bug*. This validator runs on the assembled
analyst-response envelope (what the user sees) and fails closed — routing to
analyst review — when the answer contradicts the contract or the deciders. It
does NOT silently repair, which would mask the upstream defect.

Distinct from the dormant LLM-draft Answer Guard (`app/answer_guard`): this is a
deterministic contract check that runs whenever the control plane is on, not
gated by AI_SOC_LLM_ANSWER_GUARD_ENABLED. It reuses `GuardResult` /
`AnswerGuardStatus` shapes so the trace renders uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.answer_guard.models import AnswerGuardStatus

# NOTE: this deterministic validator deliberately does NOT import
# `app.answer_guard.rules` (the dormant LLM-draft semantic guards). That module
# must stay out of the /chat import graph (see
# test_answer_guard_rules_stage3ji2). We mirror only the GuardResult *shape*
# (guard_id / status / severity / message) with a local type so the trace
# renders uniformly without coupling to the dormant guards.


@dataclass(frozen=True)
class _FinalGuardResult:
    guard_id: str
    status: str
    severity: str
    message: str
    affected_field: str | None = None


def _blocking(guard_id: str, message: str, field: str | None = None) -> _FinalGuardResult:
    return _FinalGuardResult(
        guard_id=guard_id,
        status="fail",
        severity="blocking_candidate",
        message=message,
        affected_field=field,
    )


def _ids(rows: Any) -> set[str]:
    out: set[str] = set()
    for row in rows or []:
        if isinstance(row, dict):
            value = row.get("Technique") or row.get("technique_id")
            if value:
                out.add(str(value))
    return out


def validate_final_answer(
    *,
    analyst_response: Any | None,
    answer_contract: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    mitre_decision: dict[str, Any] | None,
) -> AnswerGuardStatus:
    """Validate the assembled answer against the contract; fail closed on conflict."""
    if analyst_response is None or answer_contract is None:
        return AnswerGuardStatus(
            enabled=True,
            guard_status="skipped",
            reason="No assembled answer or contract to validate.",
        )

    contract = answer_contract
    plan = evidence_plan or {}
    decision = mitre_decision or {}
    findings: list[_FinalGuardResult] = []

    visible_mitre = _ids(getattr(analyst_response, "mitre_mappings", None))
    blocked_ids = {str(item) for item in contract.get("not_claimed_technique_ids") or []}
    answer_goal = [str(item) for item in contract.get("answer_goal") or []]
    answer_mode = str(plan.get("answer_mode") or contract.get("answer_mode") or "")
    spl_code = getattr(analyst_response, "spl_code", None)
    response_profile = str(getattr(analyst_response, "response_profile", "") or "")
    recommended = getattr(analyst_response, "recommended_actions", None) or []

    # 1. A blocked / not-claimed finding must never appear as a positive mapping.
    leaked = sorted(visible_mitre & blocked_ids)
    if leaked:
        findings.append(
            _blocking(
                "final.blocked_finding_claimed",
                f"Not-claimed technique(s) shown as a positive MITRE mapping: {', '.join(leaked)}.",
                field="mitre_mappings",
            )
        )

    # 2. MITRE must not be answer-visible when the decision suppresses it.
    if visible_mitre and not bool(contract.get("mitre_answer_visible")):
        findings.append(
            _blocking(
                "final.mitre_visible_when_suppressed",
                "MITRE mappings shown although the MITRE decision is not answer-visible.",
                field="mitre_mappings",
            )
        )

    # 3. RAG/other source must not inject techniques the decider did not surface.
    decider_ids = {str(item) for item in decision.get("registry_candidates") or []}
    for tid in (item.get("technique_id") for item in decision.get("techniques") or [] if isinstance(item, dict)):
        if tid:
            decider_ids.add(str(tid))
    injected = sorted(visible_mitre - decider_ids) if decider_ids else []
    if injected:
        findings.append(
            _blocking(
                "final.rag_override_mitre",
                f"MITRE mapping(s) not sourced from the deterministic decision: {', '.join(injected)}.",
                field="mitre_mappings",
            )
        )

    # 4. rag_only answers carry no SPL or MCP artifacts.
    if answer_mode == "rag_only" and spl_code:
        findings.append(
            _blocking(
                "final.spl_on_rag_only",
                "SPL artifact present on a rag_only (policy/knowledge) answer.",
                field="spl_code",
            )
        )

    # 5. Candidate findings must not be presented as confirmed.
    for row in getattr(analyst_response, "mitre_mappings", None) or []:
        status = str(row.get("Status") or "").lower() if isinstance(row, dict) else ""
        if status in {"confirmed", "supported"}:
            findings.append(
                _blocking(
                    "final.candidate_described_as_confirmed",
                    f"Technique {row.get('Technique')} presented as '{row.get('Status')}'; "
                    "registry mappings are candidate-only without SOC review.",
                    field="mitre_mappings",
                )
            )

    # 6. An action-guidance ask must not be answered SPL-only with no actions.
    if "analyst_action_guidance" in answer_goal and response_profile == "spl_only" and not recommended:
        findings.append(
            _blocking(
                "final.spl_only_missing_action_guidance",
                "Answer goal requested analyst action guidance but the answer is SPL-only "
                "with no recommended actions.",
                field="recommended_actions",
            )
        )

    blocking = [item for item in findings if item.severity == "blocking_candidate"]
    if blocking:
        return AnswerGuardStatus(
            enabled=True,
            guard_status="blocked",
            failed_checks=[item.guard_id for item in blocking],
            blocked_reason=blocking[0].message,
            analyst_review_required=True,
            reason="Final-answer validation failed; routing to analyst review (fail closed).",
        )
    return AnswerGuardStatus(
        enabled=True,
        guard_status="passed",
        passed_checks=[
            "final.blocked_finding_claimed",
            "final.mitre_visible_when_suppressed",
            "final.rag_override_mitre",
            "final.spl_on_rag_only",
            "final.candidate_described_as_confirmed",
            "final.spl_only_missing_action_guidance",
        ],
        reason="Final answer is consistent with the AnswerContract and the deciders.",
    )
