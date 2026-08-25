"""Explicit SPL authoring intent reconciliation (deterministic + LLM advisory)."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.intent_classification import IntentClassification
from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.config import settings
from app.spl.draft_preview import match_detection_family

_SPL_AUTHORING_INTENT_FAMILIES = frozenset({"spl_generation", "spl_generation_only"})

_UNIVERSAL_SPL_PHRASES = (
    "universal",
    "template-free",
    "template free",
    "generic spl",
    "without company",
    "without any specific company",
    "standard spl block",
    "standard universal spl",
    "spl block",
    "spl snippet",
)


def llm_advisory_indicates_spl_authoring(advisory: LLMIntentAdvisory | None) -> bool:
    if advisory is None or advisory.dropped_reasons:
        return False
    if advisory.adjudication_status == "rejected":
        return False
    if advisory.spl_authoring_request:
        return True
    family = (advisory.intent_family_candidate or "").strip().lower()
    return family in _SPL_AUTHORING_INTENT_FAMILIES


def universal_spl_phrasing(query: str) -> bool:
    normalized = (query or "").strip().lower()
    return any(term in normalized for term in _UNIVERSAL_SPL_PHRASES)


_INTENT_SKIP_REASON_UNIVERSAL_UTILITY = "intent_advisory_not_required_for_universal_utility_route"


def _spl_authoring_unsafe_signals(signals: dict[str, Any]) -> bool:
    return bool(
        signals.get("block_or_contain")
        or signals.get("explicit_run_spl")
        or signals.get("run_execution")
    )


def is_universal_utility_spl_authoring(query: str, signals: dict[str, Any]) -> bool:
    """Explicit universal/template-free SPL utility authoring (PR #58 scope)."""
    if not signals.get("explicit_spl_authoring"):
        return False
    if not universal_spl_phrasing(query):
        return False
    if _spl_authoring_unsafe_signals(signals):
        return False
    return True


def is_explicit_review_only_spl_authoring(signals: dict[str, Any] | None) -> bool:
    """True for explicit SPL-authoring asks that must stay review-only products.

    Broader than :func:`is_universal_utility_spl_authoring` (no "universal" keyword
    required). Live-data *interest* may still be present; that alone must not convert
    the product into an investigation lifecycle. Execute / contain signals disqualify.
    """
    payload = signals if isinstance(signals, dict) else {}
    if not payload.get("explicit_spl_authoring"):
        return False
    if _spl_authoring_unsafe_signals(payload):
        return False
    return True


def universal_utility_skeleton_confirmed(query: str) -> bool:
    """True when the deterministic lab family for this query is universal_timestamp_spl."""
    return match_detection_family(query) == "universal_timestamp_spl"


def should_skip_intent_for_universal_utility_spl(
    query: str,
    signals: dict[str, Any],
) -> tuple[bool, str | None]:
    """Skip intent wait only when universal utility route is deterministic and confirmed.

    If the skeleton family does not match, intent advisory remains eligible so the
    LLM can help disambiguate — fail-open to intent when unsure.
    """
    if not settings.ai_soc_llm_utility_skip_intent_advisor:
        return False, None
    if not is_universal_utility_spl_authoring(query, signals):
        return False, None
    if not universal_utility_skeleton_confirmed(query):
        return False, None
    return True, _INTENT_SKIP_REASON_UNIVERSAL_UTILITY


def source_profile_required_for_authoring(
    *,
    query: str,
    signals: dict[str, Any],
    advisory: LLMIntentAdvisory | None,
    deterministic_detected: bool,
    llm_detected: bool,
) -> bool:
    if universal_spl_phrasing(query):
        return False
    if llm_detected and advisory is not None and advisory.requires_source_profile is False:
        return False
    if llm_detected and advisory is not None and advisory.requires_source_profile is True:
        return True
    if deterministic_detected and signals.get("explicit_spl_authoring"):
        return not universal_spl_phrasing(query)
    return False


def spl_authoring_source_label(*, deterministic: bool, llm: bool) -> str | None:
    if deterministic and llm:
        return "both"
    if deterministic:
        return "deterministic"
    if llm:
        return "llm_advisory"
    return None


def build_spl_authoring_trace(
    *,
    detected: bool,
    source: str | None,
    clarification_override_suppressed: bool,
    source_profile_required: bool,
) -> dict[str, Any]:
    return {
        "explicit_spl_authoring_detected": detected,
        "spl_authoring_source": source,
        "clarification_override_suppressed": clarification_override_suppressed,
        "source_profile_required": source_profile_required,
    }


def spl_authoring_unsafe(signals: dict[str, Any], intent: IntentClassification) -> bool:
    return bool(
        signals.get("block_or_contain")
        or signals.get("explicit_run_spl")
        or signals.get("run_execution")
        or intent.primary_intent == "human_review"
    )


def reconcile_spl_authoring_intent(
    *,
    intent: IntentClassification,
    signals: dict[str, Any],
    advisory: LLMIntentAdvisory | None,
    query: str,
    build_spl_generation_classification: Any,
) -> tuple[IntentClassification, dict[str, Any]]:
    """Promote or preserve spl_generation_only for explicit SPL authoring requests."""
    deterministic = bool(signals.get("explicit_spl_authoring"))
    llm_detected = llm_advisory_indicates_spl_authoring(advisory)

    # Deterministic explicit authoring wins over a conflicting LLM downgrade.
    if deterministic and advisory is not None and not llm_advisory_indicates_spl_authoring(advisory):
        family = (advisory.intent_family_candidate or "").strip().lower()
        if family in {"knowledge_only", "clarification_required", "policy_knowledge"}:
            llm_detected = False

    detected = deterministic or llm_detected
    source = spl_authoring_source_label(deterministic=deterministic, llm=llm_detected)
    profile_required = source_profile_required_for_authoring(
        query=query,
        signals=signals,
        advisory=advisory,
        deterministic_detected=deterministic,
        llm_detected=llm_detected,
    )

    if not detected or spl_authoring_unsafe(signals, intent):
        return intent, build_spl_authoring_trace(
            detected=detected,
            source=source,
            clarification_override_suppressed=False,
            source_profile_required=profile_required,
        )

    clarified_before = intent.requires_clarification or intent.intent_family == "clarification_required"
    needs_spl_intent = (
        clarified_before
        or intent.intent_family not in _SPL_AUTHORING_INTENT_FAMILIES
        or intent.primary_intent != "spl_generation"
    )

    if needs_spl_intent:
        if deterministic:
            reason = (
                "Explicit SPL text/snippet/block request; universal review-only SPL "
                "authoring without source-profile clarification."
            )
        elif llm_detected:
            reason = (
                "LLM intent advisory recognized explicit SPL authoring; "
                "review-only SPL generation without clarification override."
            )
        else:
            reason = intent.reason
        intent = build_spl_generation_classification(reason=reason)

    return intent, build_spl_authoring_trace(
        detected=True,
        source=source,
        clarification_override_suppressed=clarified_before and not intent.requires_clarification,
        source_profile_required=profile_required,
    )
