from __future__ import annotations

from typing import Any, Callable

from pydantic import ValidationError

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.config import settings
from app.llm.adapter.output_preprocessor import INTENT_ADVISORY_SCHEMA, preprocess_llm_output
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
SKIP_NO_CONSUMER = "intent_advisory_no_consumer"


def intent_advisor_consumable(
    *,
    match_path: str | None,
    signals: dict[str, Any] | None,
    query: str,
    t0_weak_row: bool = False,
) -> tuple[bool, str | None]:
    """Return (consumable, skip_reason) for the advisory LLM hop.

    The advisory has exactly two actuation channels downstream of
    ``build_query_to_intent``: (a) ``apply_advisory_promotion`` — only possible
    when the deterministic match path is ``out_of_registry``; (b) the SPL
    authoring reconcile in ``reconcile_spl_authoring_intent`` — relevant only
    on SPL-shaped queries without unsafe execution signals. Pinned exception:
    weak/demoted T0 rows (``t0_weak_row``, the q046-guard population) keep the
    hop with their existing sharp bound rather than skipping — that trade was
    decided when the 2s frozen-T0 bound landed (PR #54) and is test-pinned.
    Every other turn spends the full advisory wall-clock (25-44s on the dev
    VPS) producing output no consumer can act on — measured at 0 actuations
    across 1279 recorded runs. Preview hints and trace display do not justify
    the hop; they degrade gracefully without it.
    """
    sig = signals or {}
    # Command-mode spines (danger-tiered MCP plan) never spend advisory budget.
    if sig.get("command_mode_active") or sig.get("explicit_run_spl"):
        return False, "intent_advisory_command_mode"
    from app.chat.answer_shape_router import classify_answer_shape

    if classify_answer_shape(query).primary_shape == "reference_taxonomy":
        # Deterministic taxonomy floor already owns the turn; promotion would
        # only fight that floor.
        return False, SKIP_NO_CONSUMER
    if match_path in {"out_of_registry", "near_105_question", "semantic_105_question"}:
        # Promotion lane (out_of_registry) or the pinned paraphrase-confirmation
        # lane (near/semantic 105 rows keep the advisor as match co-signer).
        return True, None
    if t0_weak_row:
        return True, None
    # Hybrid advisory co-sign window (source-health / process-aware OT).
    if sig.get("hybrid_advisory_source_health") or sig.get("hybrid_advisory_process_aware_ot"):
        return True, None
    normalized = (query or "").lower()
    spl_shaped = bool(
        sig.get("spl_generation")
        or sig.get("explicit_spl_authoring")
        or "spl" in normalized
        or "splunk" in normalized
    )
    unsafe = bool(
        sig.get("block_or_contain")
        or sig.get("explicit_run_spl")
        or sig.get("run_execution")
    )
    if spl_shaped and not unsafe:
        return True, None
    return False, SKIP_NO_CONSUMER


_TRUE_TOKENS = {"true", "yes", "y", "1", "t"}
_FALSE_TOKENS = {"false", "no", "n", "0", "f", "", "n/a", "na", "none", "null"}
_CONFIDENCE_WORDS = {"high": 0.9, "medium": 0.6, "med": 0.6, "moderate": 0.6, "low": 0.3, "none": 0.0}
_BOOL_FIELDS = ("paraphrase_detected", "spl_authoring_request", "llm_called")


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
    return None


def _coerce_intent_advisory_payload(payload: Any) -> tuple[dict[str, Any], list[str]]:
    """Normalize known 8B type quirks before strict schema validation.

    The JSON extractor already parses the object; small instruct models then trip
    strict pydantic on types — booleans emitted as "true"/"yes"/"n/a" and
    confidence emitted as "high"/"low" rather than floats. Coerce those in place
    so a well-formed-but-loosely-typed advisory is accepted (and recorded) instead
    of dropped as schema_invalid. Advisory remains non-authoritative either way.
    """
    if not isinstance(payload, dict):
        return {}, []
    out = dict(payload)
    warnings: list[str] = []

    for field in _BOOL_FIELDS:
        if field in out and not isinstance(out[field], bool):
            coerced = _coerce_bool(out[field])
            if coerced is None:
                out.pop(field, None)
                warnings.append(f"coerced_drop:{field}")
            else:
                out[field] = coerced
                warnings.append(f"coerced_bool:{field}")

    if "requires_source_profile" in out and out["requires_source_profile"] is not None:
        if not isinstance(out["requires_source_profile"], bool):
            coerced = _coerce_bool(out["requires_source_profile"])
            out["requires_source_profile"] = coerced  # None is a valid value here
            warnings.append("coerced_bool:requires_source_profile")

    conf = out.get("entity_slot_confidence")
    if isinstance(conf, dict):
        fixed: dict[str, float] = {}
        for key, val in conf.items():
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                fixed[str(key)] = float(val)
            elif isinstance(val, str):
                token = val.strip().lower()
                if token in _CONFIDENCE_WORDS:
                    fixed[str(key)] = _CONFIDENCE_WORDS[token]
                    warnings.append("coerced_confidence_word")
                else:
                    try:
                        fixed[str(key)] = float(token)
                    except ValueError:
                        continue
        out["entity_slot_confidence"] = fixed

    reasons = out.get("entity_slot_reasons")
    if isinstance(reasons, dict):
        out["entity_slot_reasons"] = {str(k): str(v) for k, v in reasons.items() if v is not None}

    return out, warnings


_CONSTRAINED_ABSTAIN = "none_of_these"
_CONSTRAINED_CANDIDATE_LIMIT = 5


def _constrained_intent_prompt(
    *,
    query: str,
    context_block: str,
    candidates: list[dict[str, Any]],
) -> str:
    """Candidate-constrained choice prompt (plan 2026-07-04 item 1.2).

    Promotion can only ever land a candidate the semantic index already
    suggested, so when suggestions exist the model's job is precision: pick
    one or abstain. A short choice answer is dramatically cheaper than the
    open-vocabulary extraction prompt on a slow output-token-bound model, and
    the chosen ref is registry-valid and semantic-agreeing by construction.
    Output schema is unchanged (``question_ref_candidate`` carries the choice).
    """
    options = "\n".join(
        f"- {row.get('question_ref')}: {str(row.get('question') or '').strip()}"
        for row in candidates
    )
    return (
        "You map an analyst query onto a governed SOC question registry.\n"
        f"{context_block}\n"
        f"Analyst query: {query}\n\n"
        "Choose the ONE registry question below that asks the same thing as the "
        f"analyst query, or `{_CONSTRAINED_ABSTAIN}` if none do. Do not choose a "
        "question that is merely related.\n"
        f"Options:\n{options}\n- {_CONSTRAINED_ABSTAIN}\n\n"
        "Answer with ONLY a JSON object: {\"question_ref_candidate\": \"<ref or "
        f"{_CONSTRAINED_ABSTAIN}>\", \"confidence_metadata\": {{\"confidence\": 0.0-1.0}}, "
        "\"spl_authoring_request\": true|false}"
    )


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

    constrained_candidates: list[dict[str, Any]] = []
    match_path = (candidate_mappings or {}).get("match_path")
    if match_path == "out_of_registry":
        from app.coverage.semantic_question_index import semantic_candidates

        constrained_candidates = semantic_candidates(query)[:_CONSTRAINED_CANDIDATE_LIMIT]

    if llm_raw_output_provider is None:
        context = build_governed_context_package_v1(
            query=query,
            query_understanding=query_understanding,
            candidate_mappings=candidate_mappings,
            routed_skill=routed_skill,
        )
        if constrained_candidates:
            user_prompt = _constrained_intent_prompt(
                query=query,
                context_block=context.to_prompt_block(),
                candidates=constrained_candidates,
            )
            max_tokens = 300
        else:
            user_prompt = _build_user_prompt(
                query=query,
                context_block=context.to_prompt_block(),
                prompt_mode=prompt_mode,
            )
            max_tokens = 800
        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else sidecar_timeout_seconds(INTENT_ROLE)
        )
        raw_output, timed_out, provider_label = invoke_sidecar_role(
            role=INTENT_ROLE,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
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

    pre = preprocess_llm_output(
        raw_output,
        INTENT_ADVISORY_SCHEMA,
        allow_retry=False,
        echo_of=query,
    )
    if pre.payload is None:
        return LLMIntentAdvisory(
            llm_called=True,
            dropped_reasons=[DROP_JSON_EXTRACTION_FAILED],
            adapter_warnings=[*pre.extraction_warnings, pre.verdict, *pre.validation_errors],
            provider_label=provider_label,
        )
    payload, coercion_warnings = _coerce_intent_advisory_payload(pre.payload)
    try:
        advisory = LLMIntentAdvisory.model_validate(payload)
    except ValidationError as exc:
        return LLMIntentAdvisory(
            llm_called=True,
            dropped_reasons=[DROP_SCHEMA_INVALID],
            adapter_warnings=[str(exc.errors()[0].get("type") or "schema_error")],
            provider_label=provider_label,
        )
    updates: dict[str, Any] = {
        "llm_called": True,
        "adapter_warnings": [
            *advisory.adapter_warnings,
            *pre.extraction_warnings,
            *pre.repairs,
            *coercion_warnings,
        ],
        "provider_label": provider_label,
    }
    if constrained_candidates:
        updates["confidence_metadata"] = {
            **advisory.confidence_metadata,
            "prompt_variant": "constrained_choice",
        }
        chosen = (advisory.question_ref_candidate or "").strip()
        if chosen.lower() == _CONSTRAINED_ABSTAIN:
            updates["question_ref_candidate"] = None
    return advisory.model_copy(update=updates)


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
