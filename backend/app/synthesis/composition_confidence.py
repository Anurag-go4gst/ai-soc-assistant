"""Phase 2.5 — composition confidence + HIL gate inputs for weak-case LLM bodies."""

from __future__ import annotations

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings


def qualifies_for_weak_case_composition(
    contract: AnswerContract,
    *,
    path_type: str | None = None,
    intent_family: str | None = None,
) -> bool:
    """Return True when the governed composer may narrate a weak/out-of-catalog body."""
    family = str(intent_family or contract.intent_family or "").strip()
    mode = str(contract.answer_mode or "").strip()
    if contract.out_of_catalog_notice:
        return True
    if path_type == "guided_investigation" or mode == "guided_investigation" or family == "guided_investigation":
        return True
    if family == "knowledge_only":
        return True
    if mode == "rag_only" and family not in {
        "sop_or_playbook",
        "policy_knowledge",
        "mitre_explanation",
    }:
        return True
    return False


def composition_confidence(
    *,
    contract: AnswerContract,
    path_type: str | None,
    match_path: str | None,
    soc_kb_snippet_count: int,
    skill_section_count: int,
) -> float:
    """Heuristic 0..1 score from match strength and retrieved context richness."""
    score = 0.35
    if contract.out_of_catalog_notice:
        score += 0.10
    if path_type == "guided_investigation" or contract.answer_mode == "guided_investigation":
        score += 0.10
    if match_path == "out_of_registry":
        score -= 0.12
    elif match_path in {"exact_question", "use_case"}:
        score += 0.15
    if soc_kb_snippet_count >= 2:
        score += 0.22
    elif soc_kb_snippet_count == 1:
        score += 0.12
    if skill_section_count >= 2:
        score += 0.18
    elif skill_section_count == 1:
        score += 0.10
    if contract.missing_evidence:
        score -= min(0.08, 0.02 * len(contract.missing_evidence))
    return round(min(1.0, max(0.0, score)), 3)


def compose_hil_threshold() -> float:
    return float(settings.ai_soc_llm_compose_hil_threshold)


def proposed_mcp_search_action(
    *,
    contract: AnswerContract,
    resource_decisions: list[str] | None,
    evidence_plan: dict | None,
) -> bool:
    """True when the turn proposes or allows an MCP search that must stay HIL-gated."""
    if contract.mcp_allowed:
        return True
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    summary = plan.get("resource_plan_summary") if isinstance(plan.get("resource_plan_summary"), dict) else {}
    mcp_summary = summary.get("mcp") if isinstance(summary.get("mcp"), dict) else {}
    if mcp_summary.get("allowed"):
        return True
    labels = [str(item).lower() for item in (resource_decisions or []) if item]
    return any(
        token in label
        for label in labels
        for token in ("spl_search", "mcp_search", "search_splunk", "mcp_tool")
    )


def should_attach_compose_hil(
    *,
    contract: AnswerContract,
    confidence: float,
    resource_decisions: list[str] | None,
    evidence_plan: dict | None,
) -> tuple[bool, str | None]:
    if proposed_mcp_search_action(
        contract=contract,
        resource_decisions=resource_decisions,
        evidence_plan=evidence_plan,
    ):
        return True, "proposed_mcp_search_review"
    if confidence < compose_hil_threshold():
        return True, "composition_confidence_below_threshold"
    return False, None
