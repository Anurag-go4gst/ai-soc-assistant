from __future__ import annotations

from typing import Any, Callable

from pydantic import ValidationError

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.config import settings
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.governed_context_package import build_governed_context_package_v1
from app.llm.sidecar_clients import (
    INTENT_ROLE,
    build_intent_advisory_prompt,
    invoke_sidecar_role,
    sidecar_timeout_seconds,
)
from app.llm.sidecar_governance import (
    NOTE_LLM_ASSIST_TIMED_OUT,
    SKIP_LLM_DISABLED,
    SKIP_NO_PROVIDER_CONFIGURED,
    run_sidecar_llm_with_timeout,
)
from app.query_understanding.models import QueryUnderstandingResult

DROP_JSON_EXTRACTION_FAILED = "json_extraction_failed"
DROP_SCHEMA_INVALID = "schema_invalid"
DROP_LLM_TIMED_OUT = "llm_timed_out"
DROP_ADVISOR_DISABLED = "llm_intent_advisor_disabled"


def _build_user_prompt(*, query: str, context_block: str, prompt_mode: Any | None) -> str:
    """Mode-specific prompt when a non-skip IntentPromptMode is supplied; else legacy.

    Falls back to the legacy monolithic prompt if the mode has no builder, so a
    misclassification can never drop the 2C call.
    """
    from app.chat.contracts.intent_dispatch import IntentPromptMode

    if isinstance(prompt_mode, IntentPromptMode) and prompt_mode is not IntentPromptMode.skip:
        try:
            from app.llm.intent_prompt_modes import build_mode_prompt

            return build_mode_prompt(prompt_mode, query=query, context_block=context_block)
        except ValueError:
            pass
    return build_intent_advisory_prompt(query=query, context_block=context_block)


def generate_llm_intent_advisory(
    query: str,
    *,
    query_understanding: QueryUnderstandingResult | None = None,
    llm_raw_output_provider: Callable[[], str] | None = None,
    timeout_seconds: float | None = None,
    allow_failover: bool = True,
    candidate_mappings: dict[str, Any] | None = None,
    routed_skill: str | None = None,
    prompt_mode: Any | None = None,
) -> LLMIntentAdvisory:
    """Return a non-authoritative intent advisory.

    Production path uses Qwen/local primary with Foundation-Sec Instruct failover.
    Tests may inject ``llm_raw_output_provider``; otherwise a governed sidecar client
    is used when configured.

    ``prompt_mode`` (IntentPromptMode) selects a table-driven, focused prompt when
    the pipeline-dispatch flag is on; ``None`` keeps the legacy monolithic prompt
    (flag-off byte-identical).
    """
    if not settings.ai_soc_llm_intent_advisor_enabled:
        return LLMIntentAdvisory(dropped_reasons=[DROP_ADVISOR_DISABLED])
    if not settings.ai_soc_llm_enabled or settings.ai_soc_llm_mode.strip().lower() == "disabled":
        return LLMIntentAdvisory(dropped_reasons=[SKIP_LLM_DISABLED])

    provider_label: str | None = None
    raw_output: str | None = None
    timed_out = False

    if llm_raw_output_provider is None:
        context = build_governed_context_package_v1(
            query=query,
            query_understanding=query_understanding,
            candidate_mappings=candidate_mappings,
            routed_skill=routed_skill,
        )
        user_prompt = _build_user_prompt(
            query=query,
            context_block=context.to_prompt_block(),
            prompt_mode=prompt_mode,
        )
        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else sidecar_timeout_seconds(INTENT_ROLE)
        )
        raw_output, timed_out, provider_label = invoke_sidecar_role(
            role=INTENT_ROLE,
            user_prompt=user_prompt,
            max_tokens=800,
            timeout_seconds=effective_timeout,
            temperature=0.0,
            allow_failover=allow_failover,
        )
        if raw_output is None and not timed_out:
            return LLMIntentAdvisory(dropped_reasons=[SKIP_NO_PROVIDER_CONFIGURED])
    else:
        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else sidecar_timeout_seconds(INTENT_ROLE)
        )
        call = run_sidecar_llm_with_timeout(
            llm_raw_output_provider,
            timeout_seconds=effective_timeout,
        )
        timed_out = call.timed_out
        raw_output = call.raw_output

    if timed_out or not raw_output:
        return LLMIntentAdvisory(
            llm_called=True,
            dropped_reasons=[DROP_LLM_TIMED_OUT],
            adapter_warnings=[NOTE_LLM_ASSIST_TIMED_OUT],
            provider_label=provider_label,
        )

    extraction = extract_first_json_object(raw_output)
    if not extraction.parsed_ok or extraction.payload is None:
        return LLMIntentAdvisory(
            llm_called=True,
            dropped_reasons=[DROP_JSON_EXTRACTION_FAILED],
            adapter_warnings=[*extraction.warnings, *extraction.errors],
            provider_label=provider_label,
        )
    try:
        advisory = LLMIntentAdvisory.model_validate(extraction.payload)
    except ValidationError as exc:
        return LLMIntentAdvisory(
            llm_called=True,
            dropped_reasons=[DROP_SCHEMA_INVALID],
            adapter_warnings=[str(exc.errors()[0].get("type") or "schema_error")],
            provider_label=provider_label,
        )
    return advisory.model_copy(
        update={
            "llm_called": True,
            "adapter_warnings": [*advisory.adapter_warnings, *extraction.warnings],
            "provider_label": provider_label,
        }
    )


def adjudicate_llm_intent_advisory(
    advisory: LLMIntentAdvisory | None,
    *,
    query_understanding: QueryUnderstandingResult | None,
    candidate_mappings: dict[str, Any],
) -> LLMIntentAdvisory | None:
    if advisory is None:
        return None
    if advisory.dropped_reasons:
        return advisory.model_copy(
            update={
                "adjudication_status": "skipped",
                "adjudication_reason": "advisor_not_available",
            }
        )

    known_question = _known_question(query_understanding, candidate_mappings)
    known_use_cases = _known_use_cases(query_understanding, candidate_mappings)
    question = advisory.question_ref_candidate
    use_case = advisory.use_case_id_candidate

    if question and known_question and question != known_question:
        return advisory.model_copy(
            update={
                "adjudication_status": "corrected",
                "adjudication_reason": "deterministic_question_ref_wins",
                "question_ref_candidate": known_question,
            }
        )
    if use_case and known_use_cases and use_case not in known_use_cases:
        return advisory.model_copy(
            update={
                "adjudication_status": "corrected",
                "adjudication_reason": "deterministic_use_case_wins",
                "use_case_id_candidate": known_use_cases[0],
            }
        )
    if question and not _candidate_question_allowed(question, known_question):
        return advisory.model_copy(
            update={
                "adjudication_status": "rejected",
                "adjudication_reason": "question_ref_candidate_not_in_deterministic_registry",
            }
        )
    if use_case and not _candidate_use_case_allowed(use_case, known_use_cases):
        return advisory.model_copy(
            update={
                "adjudication_status": "rejected",
                "adjudication_reason": "use_case_id_candidate_not_in_deterministic_registry",
            }
        )
    return advisory.model_copy(
        update={
            "adjudication_status": "accepted",
            "adjudication_reason": "advisory_normalized_through_deterministic_context",
        }
    )


def _known_question(
    query_understanding: QueryUnderstandingResult | None,
    candidate_mappings: dict[str, Any],
) -> str | None:
    value = candidate_mappings.get("question_ref")
    if isinstance(value, str) and value:
        return value
    if query_understanding and query_understanding.mapped_question_ref:
        return query_understanding.mapped_question_ref
    return None


def _known_use_cases(
    query_understanding: QueryUnderstandingResult | None,
    candidate_mappings: dict[str, Any],
) -> list[str]:
    values = candidate_mappings.get("use_case_ids")
    if isinstance(values, list):
        return [str(item) for item in values if item]
    if query_understanding:
        return list(query_understanding.mapped_use_case_ids or [])
    return []


def _candidate_question_allowed(candidate: str, known_question: str | None) -> bool:
    if known_question:
        return candidate == known_question
    # WS1 T1.3: when deterministic intake found nothing, a candidate is
    # acceptable iff it names a real registry row — promotion applies the
    # remaining gates (confidence, semantic agree/abstain, unsafe veto).
    from app.coverage.question_runtime_map import question_runtime_entry

    return question_runtime_entry(candidate) is not None


def _candidate_use_case_allowed(candidate: str, known_use_cases: list[str]) -> bool:
    if known_use_cases:
        return candidate in known_use_cases
    from app.use_cases.registry import load_use_case_catalog

    return candidate in {item.use_case_id for item in load_use_case_catalog()}



PROMOTION_MIN_CONFIDENCE = 0.75


def apply_advisory_promotion(
    *,
    advisory: LLMIntentAdvisory | None,
    candidate_mappings: dict[str, Any],
    intent_requires_clarification: bool,
    intent_requires_hil: bool,
    query: str,
) -> tuple[dict[str, Any], LLMIntentAdvisory | None]:
    """Promote a validated advisory candidate when deterministic intake found
    nothing (WS1 T1.3).

    Promotion conditions (ALL must hold):
    - deterministic match path is out_of_registry (deterministic has nothing
      to defend — exact/near/semantic/catalog rungs always win otherwise)
    - the advisory survived adjudication ("accepted": candidate ids already
      validated against the deterministic registries)
    - candidate confidence >= PROMOTION_MIN_CONFIDENCE
    - the semantic tier agrees or abstains: candidate ref appears in the top
      semantic candidates, or there are no candidates at all
    - the classified intent did not require clarification or human review
      (unsafe/clarification outcomes override promotion entirely)

    Effect is mapping-level only: match_path becomes
    "llm_promoted_with_registry_validation" and the candidate ref/use-case is
    recorded. Severity, MITRE, SPL, and execution authority are untouched.
    """
    if advisory is None or advisory.adjudication_status != "accepted":
        return candidate_mappings, advisory
    if str(candidate_mappings.get("match_path") or "") != "out_of_registry":
        return candidate_mappings, advisory
    if intent_requires_clarification or intent_requires_hil:
        return candidate_mappings, advisory

    candidate_ref = advisory.question_ref_candidate
    candidate_use_case = advisory.use_case_id_candidate
    if not candidate_ref and not candidate_use_case:
        return candidate_mappings, advisory

    confidence = advisory.confidence_metadata.get("confidence")
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    if confidence_value < PROMOTION_MIN_CONFIDENCE:
        return candidate_mappings, advisory

    if candidate_ref:
        from app.coverage.question_runtime_map import question_runtime_entry
        from app.coverage.semantic_question_index import semantic_candidates

        entry = question_runtime_entry(candidate_ref)
        if entry is None:
            return candidate_mappings, advisory
        suggestions = [item["question_ref"] for item in semantic_candidates(query)]
        if suggestions and candidate_ref not in suggestions:
            return candidate_mappings, advisory
        promoted = {
            **candidate_mappings,
            "match_path": "llm_promoted_with_registry_validation",
            "question_ref": candidate_ref,
        }
    else:
        from app.use_cases.registry import load_use_case_catalog

        catalog_ids = {item.use_case_id for item in load_use_case_catalog()}
        if candidate_use_case not in catalog_ids:
            return candidate_mappings, advisory
        promoted = {
            **candidate_mappings,
            "match_path": "llm_promoted_with_registry_validation",
            "use_case_ids": [candidate_use_case, *candidate_mappings.get("use_case_ids", [])],
        }

    return promoted, advisory.model_copy(
        update={
            "adjudication_status": "promoted",
            "adjudication_reason": "out_of_registry_candidate_promoted_after_registry_validation",
        }
    )
