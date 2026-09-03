"""FINAL EFFECTIVE STATE projection for the debug bundle.

The bundle carries several independent read models, each written at a different
stage. Read together they can contradict each other: an intermediate stage that
raised a clarification, a later stage that resolved it, and a summary builder
that picked whichever field it happened to own. This module is the single place
that resolves those into one internally consistent story for the run.

Precedence (later wins on conflict), mirroring the runtime authority order:

    resolved query / intent
      -> final ResourcePlan
      -> final source-profile resolution
      -> final SPL authoring / fidelity result
      -> final execution + HIL adjudication
      -> final synthesis result
      -> final output projection

Nothing here is authority. It reads an already-serialized response payload and
never mutates state, never decides HIL, execution eligibility, RBAC, routing or
validation. Legacy fields keep their original meaning and are echoed under
``legacy_*`` names so existing consumers are unaffected; the canonical fields are
additive. Intermediate values stay in ``control_plane_trace`` and the timeline --
this projection only marks which of them the final adjudication superseded.
"""

from __future__ import annotations

import re
from typing import Any

from app.spl.spl_provenance_trace import is_deterministic_spl_provider, llm_used_factual

SCHEMA_VERSION = "trace_effective_state_v1"

AUTHORITY_NOTE = "Final adjudicated read model over governed state; never execution authority."

PRECEDENCE: tuple[str, ...] = (
    "resolved_query_contract",
    "resource_plan",
    "source_profile_resolution",
    "spl_authoring_fidelity",
    "execution_and_hil_adjudication",
    "synthesis",
    "final_output",
)

#: Answer modes whose deliverable is an SPL artifact for review, not an answer
#: derived from executed telemetry.
_REVIEW_ONLY_ANSWER_MODES = frozenset({"spl_utility_authoring", "spl_review_only"})

#: HIL kinds that a later source-profile resolution is allowed to supersede for
#: the current turn. Any other review kind passes through untouched.
_SOURCE_PROFILE_REVIEW_KINDS = frozenset({"spl_source_profile_clarification"})

#: Validator reject reason that means "deliberately withheld from execution
#: promotion", not "this SPL is defective".
_REVIEW_ONLY_WITHHOLD_REASON = "review_only_spl_authoring"

#: Ordered LLM SPL-candidate lifecycle steps, and the step each recorded
#: authoring-failure stage fails at.
_CANDIDATE_STEPS: tuple[str, ...] = (
    "transport_completed",
    "parsed",
    "schema_valid",
    "quality_passed",
    "fidelity_passed",
)
_STAGE_FAILS_AT: dict[str, str] = {
    "provider": "transport_completed",
    "json_parse": "parsed",
    "schema_validation": "schema_valid",
    "content_validation": "quality_passed",
    "draft_quality": "quality_passed",
}

#: EvidencePlan keys that are catalogue/planning metadata for every answer mode.
#: Presence here never means the runtime needed them to produce the answer.
_PLANNING_METADATA_KEYS: tuple[str, ...] = (
    "answer_rules",
    "checklist",
    "correlation",
    "evidence_legs",
    "investigation_workflow",
    "limitations",
    "mitre_candidates_metadata_only",
    "recommended_pivots",
    "unsupported_claims_avoid",
)

_NOT_REACHED = "not_reached"


def _dig(payload: Any, *keys: str) -> Any:
    """Walk nested mappings, returning None the moment the path breaks."""
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_effective_state_projection(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve the bundle's competing read models into one final effective state.

    ``payload`` is a serialized chat response (``response.model_dump(mode="json")``).
    Every block is tolerant of missing keys and this function never raises, so a
    telemetry projection can never break chat.
    """
    if not isinstance(payload, dict):
        return {}
    try:
        return _build(payload)
    except Exception:  # noqa: BLE001 - a diagnostic projection must never break chat
        return {
            "schema_version": SCHEMA_VERSION,
            "authority_note": AUTHORITY_NOTE,
            "projection_status": "failed",
        }


def _build(payload: dict[str, Any]) -> dict[str, Any]:
    trace = _as_dict(payload.get("control_plane_trace"))
    run_contract = _as_dict(payload.get("run_contract"))
    evidence_plan = _as_dict(trace.get("evidence_plan")) or _as_dict(payload.get("evidence_plan"))
    candidate_spl = _as_dict(payload.get("candidate_spl"))
    authoring = _as_dict(candidate_spl.get("utility_spl_draft_trace"))
    postprocessor = _as_dict(candidate_spl.get("review_only_spl_postprocessor_trace")) or _as_dict(
        authoring.get("review_only_spl_postprocessor_trace")
    )
    handoff = _as_dict(trace.get("spl_artifact_handoff_summary"))
    signals = _as_dict(_dig(trace, "query_to_intent", "query_signals"))

    review_only = _review_only_context(
        payload=payload,
        run_contract=run_contract,
        handoff=handoff,
        signals=signals,
    )
    source_profile = _source_profile_block(
        evidence_plan=evidence_plan,
        postprocessor=postprocessor,
        final_spl=str(candidate_spl.get("candidate_spl") or ""),
        review_only=review_only,
    )
    spl_authoring = _spl_authoring_block(
        candidate_spl=candidate_spl,
        authoring=authoring,
        postprocessor=postprocessor,
        handoff=handoff,
        run_contract=run_contract,
    )
    execution = _execution_block(payload=payload, trace=trace, run_contract=run_contract, review_only=review_only)
    hil = _hil_block(
        payload=payload,
        trace=trace,
        run_contract=run_contract,
        evidence_plan=evidence_plan,
        source_profile=source_profile,
        review_only=review_only,
        spl_authoring=spl_authoring,
    )
    synthesis = _synthesis_block(authoring=authoring, trace=trace, review_only=review_only)
    rag = _rag_block(trace=trace, evidence_plan=evidence_plan, payload=payload)
    evidence = _evidence_block(
        payload=payload,
        run_contract=run_contract,
        execution=execution,
        spl_authoring=spl_authoring,
        rag=rag,
    )
    validation = _validation_block(
        payload=payload,
        run_contract=run_contract,
        handoff=handoff,
        authoring=authoring,
        spl_authoring=spl_authoring,
        review_only=review_only,
    )
    candidate_lifecycle = _candidate_lifecycle_block(authoring=authoring, trace=trace)
    llm = _llm_block(
        payload=payload,
        trace=trace,
        candidate_lifecycle=candidate_lifecycle,
        synthesis=synthesis,
        spl_authoring=spl_authoring,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "authority_note": AUTHORITY_NOTE,
        "precedence": list(PRECEDENCE),
        "answer_mode": review_only["answer_mode"],
        "review_only": review_only["review_only"],
        "explicit_do_not_execute": review_only["explicit_do_not_execute"],
        "hil": hil,
        "source_profile": source_profile,
        "spl_authoring": spl_authoring,
        "llm_spl_candidate_lifecycle": candidate_lifecycle,
        "synthesis": synthesis,
        "rag": rag,
        "evidence": evidence,
        "validation": validation,
        "llm": llm,
        "execution": execution,
        "evidence_plan_classification": _evidence_plan_classification(evidence_plan),
        "status": _status_block(payload=payload, hil=hil, spl_authoring=spl_authoring, execution=execution),
    }


def _review_only_context(
    *,
    payload: dict[str, Any],
    run_contract: dict[str, Any],
    handoff: dict[str, Any],
    signals: dict[str, Any],
) -> dict[str, Any]:
    """Decide, from governed signals only, whether this turn is review-only.

    Never parses the user's text: `review_only_spl` / `run_execution` /
    `explicit_run_spl` are the deterministic query signals the router already
    committed, and `execution_needed_for_answer` is the RunContract's own verdict.
    """
    answer_mode = payload.get("answer_mode") or _dig(payload, "evidence_plan", "answer_mode")
    answer_mode = str(answer_mode) if answer_mode else None
    review_only = bool(
        handoff.get("review_only")
        or (answer_mode in _REVIEW_ONLY_ANSWER_MODES)
        or signals.get("review_only_spl")
    )
    execution_asked = bool(
        signals.get("run_execution") or signals.get("explicit_run_spl") or signals.get("run_spl")
    )
    explicit_do_not_execute = bool(
        review_only and not execution_asked and run_contract.get("execution_needed_for_answer") is not True
    )
    return {
        "answer_mode": answer_mode,
        "review_only": review_only,
        "execution_requested_by_user": execution_asked,
        "explicit_do_not_execute": explicit_do_not_execute,
    }


def _source_profile_block(
    *,
    evidence_plan: dict[str, Any],
    postprocessor: dict[str, Any],
    final_spl: str,
    review_only: dict[str, Any],
) -> dict[str, Any]:
    """Separate what the source profile *resolved* from what the draft *shows*.

    A review-only draft may deliberately display `<your_index>` while the profile
    store resolved a real index. Reporting only "binding applied = pgcil_soc" next
    to a rendered placeholder is what made the bundle unreadable, so each slot
    carries the resolved value, the displayed value, and why they differ.
    """
    summary = _as_dict(evidence_plan.get("source_profile_binding_summary"))
    applied = [item for item in _as_list(summary.get("source_profile_bindings_applied")) if isinstance(item, dict)]
    found = [item for item in _as_list(summary.get("source_profile_bindings_found")) if isinstance(item, dict)]
    missing = [str(item) for item in _as_list(summary.get("source_profile_bindings_missing"))]

    placeholder_used = bool(postprocessor.get("placeholder_used"))
    rewrite_reason = postprocessor.get("index_rewrite_reason")
    slots: dict[str, Any] = {}
    for binding in applied or found:
        slot = str(binding.get("slot") or "").strip()
        if not slot:
            continue
        resolved_value = binding.get("value")
        exposed = bool(resolved_value) and str(resolved_value) in final_spl
        drafted = _drafted_slot_value(final_spl, slot)
        display_value: Any = str(resolved_value) if exposed else drafted
        withholding_reason: str | None = None
        if not exposed:
            if display_value is None and slot == "index":
                display_value = postprocessor.get("resolved_index")
            # A placeholder token is a deliberate review-only substitution. A
            # different concrete value is not withholding at all -- the draft
            # simply bound something else (e.g. a user-explicit index), and
            # calling that "placeholder policy" would be a new false statement.
            if _is_placeholder(display_value):
                withholding_reason = "review_only_placeholder_policy"
            elif display_value:
                withholding_reason = "draft_uses_different_value"
            else:
                withholding_reason = "not_present_in_draft"
        slots[slot] = {
            "resolved_value": resolved_value,
            "resolution_source": binding.get("source"),
            "profile_key": binding.get("profile_key"),
            "resolved": True,
            "binding_found": True,
            "binding_allowed_for_runtime": True,
            "binding_applied_to_internal_candidate": True,
            "exposed_in_review_draft": exposed,
            "display_value": display_value,
            "withholding_reason": withholding_reason,
        }
    for slot in missing:
        slots.setdefault(
            str(slot),
            {
                "resolved_value": None,
                "resolution_source": None,
                "profile_key": None,
                "resolved": False,
                "binding_found": False,
                "binding_allowed_for_runtime": False,
                "binding_applied_to_internal_candidate": False,
                "exposed_in_review_draft": False,
                "display_value": None,
                "withholding_reason": "binding_missing",
            },
        )
    withheld = sorted(
        name
        for name, slot in slots.items()
        if slot["resolved"] and slot["withholding_reason"] == "review_only_placeholder_policy"
    )
    unbound = sorted(
        token
        for token in _placeholder_tokens(final_spl)
        if not any(_is_placeholder(slot["display_value"]) and slot["display_value"] == token for slot in slots.values())
    )
    return {
        "lookup_attempted": bool(summary.get("source_profile_lookup_attempted")),
        "environment_knowledge_lookup_attempted": bool(summary.get("environment_knowledge_lookup_attempted")),
        "bindings_missing": missing,
        "all_required_bindings_resolved": not missing,
        "slots": slots,
        "slots_resolved_but_withheld_from_review_draft": withheld,
        # Placeholder tokens the draft still shows that no binding record covers.
        # `bindings_missing == []` on its own would otherwise read as "fully bound"
        # for a draft the analyst still has to fill in before execution.
        "unbound_placeholders_in_review_draft": unbound,
        "review_draft_fully_bound": not unbound and not withheld,
        "review_draft_placeholder_used": placeholder_used,
        "index_resolution_source": postprocessor.get("index_resolution_source"),
        "index_rewrite_applied": bool(postprocessor.get("index_rewrite_applied")),
        "index_rewrite_reason": rewrite_reason,
    }


def _is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return text.startswith("<") and text.endswith(">")


def _placeholder_tokens(spl: str) -> set[str]:
    """Every `<slot>` token still present in the rendered draft."""
    return set(re.findall(r"<[A-Za-z0-9_.:-]+>", spl or ""))


def _drafted_slot_value(spl: str, slot: str) -> str | None:
    """The value the rendered draft actually shows for `slot=...`, if any."""
    match = re.search(rf"\b{re.escape(slot)}\s*=\s*(\S+)", spl or "")
    return match.group(1) if match else None


def _spl_authoring_block(
    *,
    candidate_spl: dict[str, Any],
    authoring: dict[str, Any],
    postprocessor: dict[str, Any],
    handoff: dict[str, Any],
    run_contract: dict[str, Any],
) -> dict[str, Any]:
    fidelity = _as_dict(authoring.get("semantic_fidelity_final")) or _as_dict(
        authoring.get("semantic_fidelity_compiler")
    )
    has_fidelity = bool(fidelity)
    artifact_present = bool(
        str(candidate_spl.get("candidate_spl") or "").strip()
        or handoff.get("artifact_present")
        or run_contract.get("spl_candidate_present")
    )
    return {
        "spl_artifact_available": artifact_present,
        "final_spl_authority": authoring.get("final_spl_authority") or postprocessor.get("final_spl_authority"),
        "final_raw_spl_source": authoring.get("final_raw_spl_source") or candidate_spl.get("final_raw_spl_source"),
        "authoring_source": authoring.get("authoring_source"),
        "legacy_compiler_rescue": bool(authoring.get("legacy_compiler_rescue")),
        "deterministic_compiler_used": bool(authoring.get("deterministic_compiler_used")),
        "generation_mode": candidate_spl.get("generation_mode"),
        "authoring_fidelity_status": ("passed" if fidelity.get("passed") else "failed") if has_fidelity else "not_run",
        "authoring_fidelity_losses": [str(item) for item in _as_list(fidelity.get("losses"))],
        "postprocessor_applied": bool(postprocessor.get("postprocessor_applied")),
        "postprocessor_changes": [str(item) for item in _as_list(postprocessor.get("changes"))],
        "final_spl_hash": postprocessor.get("normalized_spl_hash"),
        "raw_spl_hash": postprocessor.get("raw_spl_hash"),
    }


def _candidate_lifecycle_block(*, authoring: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    """Expand the LLM SPL advisory into an ordered lifecycle.

    `requested=true` alongside `completed=false`, `generated=false` and
    `outcome=dropped` compresses several different failures into one shape. The
    recorded `authoring_failure_stage` says exactly where the candidate stopped,
    so each step reports true / false / not_reached instead.
    """
    generation = _as_dict(trace.get("candidate_spl_generation"))
    requested = bool(
        authoring.get("llm_spl_draft_requested")
        if "llm_spl_draft_requested" in authoring
        else generation.get("llm_spl_draft_requested")
    )
    used = bool(
        authoring.get("llm_spl_draft_used")
        if "llm_spl_draft_used" in authoring
        else generation.get("llm_spl_draft_used")
    )
    stage = str(authoring.get("authoring_failure_stage") or "") or None
    steps: dict[str, Any] = {}
    if not requested:
        steps = {name: _NOT_REACHED for name in _CANDIDATE_STEPS}
    elif used:
        steps = {name: True for name in _CANDIDATE_STEPS}
    else:
        fails_at = _STAGE_FAILS_AT.get(stage or "")
        if fails_at is None:
            # No recorded stage: report unknown rather than inventing a boundary.
            steps = {name: None for name in _CANDIDATE_STEPS}
        else:
            reached = True
            for name in _CANDIDATE_STEPS:
                if name == fails_at:
                    steps[name] = False
                    reached = False
                else:
                    steps[name] = True if reached else _NOT_REACHED
    if steps.get("fidelity_passed") is True and authoring.get("llm_pattern_success") is False:
        steps["fidelity_passed"] = False
    return {
        "requested": requested,
        **steps,
        "used": used,
        "failure_stage": stage,
        "failure_code": authoring.get("authoring_failure_code"),
        "dropped_reason": authoring.get("llm_spl_draft_dropped_reason")
        or generation.get("llm_spl_draft_skipped_reason"),
        "timed_out": bool(authoring.get("llm_spl_draft_timed_out") or generation.get("llm_spl_draft_timed_out")),
        "latency_ms": _int_or_none(authoring.get("llm_spl_draft_latency_ms")),
        "provider_label": authoring.get("llm_spl_draft_provider_label"),
        "model": generation.get("llm_model"),
        "repair_attempted": bool(authoring.get("bounded_repair_attempted")),
        "repair_used": bool(authoring.get("bounded_repair_used")),
        "pattern_selected": bool(authoring.get("pattern_selected")),
        "pattern_id": authoring.get("pattern_id"),
        "pattern_success": bool(authoring.get("llm_pattern_success")),
        "candidate_validator_result": _as_dict(authoring.get("validator_result")) or None,
    }


def _synthesis_block(
    *, authoring: dict[str, Any], trace: dict[str, Any], review_only: dict[str, Any]
) -> dict[str, Any]:
    """Name what produced the analyst prose.

    The composer block reports `composer_attempted=false` / `narration_calls=0`
    because the review-only card is narrated by its own governed synthesis path,
    not the chat composer. Without this block the provenance of the summary /
    "What this query does" / mappings text is unrecoverable from the bundle.
    """
    source = authoring.get("analyst_synthesis_source")
    dropped = [str(item) for item in _as_list(authoring.get("analyst_synthesis_dropped_reasons"))]
    present = bool(_as_dict(authoring.get("analyst_synthesis")))
    if source is None and not present:
        composer = _as_dict(trace.get("llm_composer"))
        return {
            "synthesis_attempted": bool(composer.get("composer_attempted")),
            "synthesis_source": "LLM_COMPOSER" if composer.get("llm_composer_used") else None,
            "synthesis_model": None,
            "synthesis_status": "not_applicable",
            "synthesis_latency_ms": None,
            "synthesis_validation_status": "not_run",
            "synthesis_fallback_reason": [str(composer.get("llm_blocked_reason"))]
            if composer.get("llm_blocked_reason")
            else [],
            "synthesis_grounding_status": "not_applicable",
            "composer_attempted": bool(composer.get("composer_attempted")),
            "composer_used": bool(composer.get("llm_composer_used")),
            "composer_blocked_reason": composer.get("llm_blocked_reason"),
        }
    llm_attempted = bool(authoring.get("analyst_synthesis_llm_attempted"))
    is_llm = source == "LLM_SYNTHESIS"
    composer = _as_dict(trace.get("llm_composer"))
    return {
        "synthesis_attempted": bool(llm_attempted or present),
        "synthesis_source": source,
        "synthesis_model": composer.get("ai_soc_llm_mode") if is_llm else None,
        "synthesis_status": "llm_accepted" if is_llm else "deterministic_fallback_used",
        "synthesis_latency_ms": _int_or_none(authoring.get("analyst_synthesis_latency_ms")),
        # A dropped LLM draft means the fallback text was never validated against a
        # model output; the deterministic composer is grounded by construction.
        "synthesis_validation_status": "passed" if is_llm else "not_run",
        "synthesis_fallback_reason": dropped,
        "synthesis_grounding_status": (
            "validated_against_spec_and_spl" if is_llm else "deterministic_from_governed_spec"
        ),
        "llm_call_attempted": llm_attempted,
        "spl_immutable": True,
        "review_only": review_only["review_only"],
        "composer_attempted": bool(composer.get("composer_attempted")),
        "composer_used": bool(composer.get("llm_composer_used")),
        "composer_blocked_reason": composer.get("llm_blocked_reason"),
    }


def _rag_block(
    *, trace: dict[str, Any], evidence_plan: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    """Classify a retrieval the plan did not ask for, rather than hiding it.

    A lookup performed by `spl_source_resolve` exists to hint source-profile slots.
    It is a real event and stays in the trace, but it is enrichment, not runtime
    investigation RAG, and must not be read as evidence behind the answer.
    """
    rag_trace = _as_dict(trace.get("rag_trace"))
    needs_rag = evidence_plan.get("needs_rag")
    status = str(rag_trace.get("retrieval_status") or rag_trace.get("match_status") or "") or None
    retrieved = status == "retrieved"
    stage = rag_trace.get("retrieval_workflow_stage")
    skipped_for_authoring = bool(rag_trace.get("rag_skipped_for_spl_utility_authoring"))
    runtime_rag_used = bool(retrieved and needs_rag is True)
    enrichment_used = bool(retrieved and not runtime_rag_used)
    if enrichment_used:
        reason = "retrieval_outside_planned_rag_need"
        if stage:
            reason = f"retrieval_performed_at_stage:{stage}"
    elif runtime_rag_used:
        reason = "planned_runtime_rag"
    elif skipped_for_authoring:
        reason = "rag_skipped_for_spl_utility_authoring"
    else:
        reason = "no_retrieval"
    knowledge_records = [
        record
        for record in _as_list(payload.get("source_evidence"))
        if isinstance(record, dict) and str(record.get("source_type") or "") == "rag"
    ]
    return {
        "planned_needs_rag": needs_rag,
        "planned_rag_phase": evidence_plan.get("rag_phase"),
        "retrieval_status": status,
        "retrieval_workflow_stage": stage,
        "retrieval_mode": rag_trace.get("retrieval_mode"),
        "retrieval_backend": rag_trace.get("retrieval_backend"),
        "runtime_rag_used": runtime_rag_used,
        "enrichment_lookup_used": enrichment_used,
        "enrichment_source": rag_trace.get("retrieval_mode") or rag_trace.get("retrieval_backend")
        if enrichment_used
        else None,
        "enrichment_purpose": "source_profile_hint" if enrichment_used and stage == "spl_source_resolve" else None,
        "classification_reason": reason,
        "knowledge_record_count": len(knowledge_records),
        "retrieval_result_count": len(knowledge_records),
        "allowed_to_ground_final_analytic_answer": bool(runtime_rag_used),
    }


def _evidence_block(
    *,
    payload: dict[str, Any],
    run_contract: dict[str, Any],
    execution: dict[str, Any],
    spl_authoring: dict[str, Any],
    rag: dict[str, Any],
) -> dict[str, Any]:
    """State plainly which kinds of evidence this turn actually has.

    `executed_evidence` means evidence produced by an execution. `spl` in the raw
    EvidenceState means an executed SPL *result*, which a review-only draft never
    produces -- so the artifact is reported on its own key instead of leaving a
    rendered SPL looking like a gap.
    """
    state = _as_dict(payload.get("evidence_state")) or _as_dict(
        _dig(payload, "control_plane_trace", "evidence_state")
    )
    obtained = [str(item) for item in _as_list(state.get("obtained"))]
    missing = [str(item) for item in _as_list(state.get("missing"))]
    executed = bool(execution["execution_performed"])
    live_available = bool(executed and execution["result_count"])
    knowledge_available = bool(rag["knowledge_record_count"]) or "rag" in obtained
    return {
        "executed_evidence": {
            "status": "obtained" if live_available else "not_applicable",
            "reason": None if live_available else "no_execution_performed",
            "execution_status": execution["mcp_status"],
            "result_count": execution["result_count"],
        },
        "spl_artifact": {
            "status": "obtained" if spl_authoring["spl_artifact_available"] else "missing",
            "execution_eligible": execution["execution_eligible"],
        },
        "spl_execution_result": {
            "status": "obtained" if live_available else "not_applicable",
            "reason": None if live_available else "review_only_no_execution",
        },
        "live_execution_evidence_available": live_available,
        "artifact_evidence_available": bool(spl_authoring["spl_artifact_available"]),
        "knowledge_evidence_available": knowledge_available,
        "legacy_source_evidence_available": bool(run_contract.get("source_evidence_available")),
        "legacy_source_evidence_definition": (
            "true when any SourceEvidence record exists, including knowledge/reference records; "
            "not a claim about live telemetry"
        ),
        "evidence_state_obtained": obtained,
        "evidence_state_missing": missing,
        "required_key_semantics": {
            str(item.get("key")): item.get("applicability")
            for item in _as_list(state.get("items"))
            if isinstance(item, dict) and item.get("applicability")
        },
    }


def _validation_block(
    *,
    payload: dict[str, Any],
    run_contract: dict[str, Any],
    handoff: dict[str, Any],
    authoring: dict[str, Any],
    spl_authoring: dict[str, Any],
    review_only: dict[str, Any],
) -> dict[str, Any]:
    """Split authoring validation from execution promotion.

    `spl_validated=false` / `validator_status=rejected` describes the execution
    promotion refusal on the lab-candidate envelope. Applied to the compiler SPL
    that was authored, fidelity-checked and deliberately displayed, it reads as a
    defect that does not exist.
    """
    spl_validation = _as_dict(payload.get("spl_validation"))
    reject_reasons = [str(item) for item in _as_list(spl_validation.get("reject_reasons"))]
    approved = bool(spl_validation.get("approved"))
    withheld_review_only = _REVIEW_ONLY_WITHHOLD_REASON in reject_reasons
    other_rejections = [item for item in reject_reasons if item != _REVIEW_ONLY_WITHHOLD_REASON]

    if approved:
        candidate_status = "passed"
    elif withheld_review_only and not other_rejections:
        candidate_status = "withheld_review_only"
    elif reject_reasons:
        candidate_status = "failed"
    else:
        candidate_status = "not_available"

    if review_only["explicit_do_not_execute"] or (withheld_review_only and not other_rejections):
        execution_status = "not_applicable_review_only"
    elif approved:
        execution_status = "approved"
    elif reject_reasons:
        execution_status = "rejected"
    else:
        execution_status = "not_run"

    candidate_validator = _as_dict(authoring.get("validator_result"))
    return {
        "authoring_fidelity_status": spl_authoring["authoring_fidelity_status"],
        "authoring_fidelity_losses": spl_authoring["authoring_fidelity_losses"],
        "candidate_spl_validation_status": candidate_status,
        "candidate_spl_validation_reasons": reject_reasons,
        "candidate_spl_validation_subject": "execution_promotion_envelope",
        "final_spl_rejected_by_validator": bool(other_rejections),
        "final_spl_source": spl_authoring["final_raw_spl_source"],
        "llm_candidate_validation_status": (
            "passed"
            if candidate_validator.get("lab_candidate_eligible")
            else "failed"
            if candidate_validator
            else "not_run"
        ),
        "llm_candidate_validation_reasons": [
            str(item) for item in _as_list(candidate_validator.get("reject_reasons"))
        ],
        "execution_validation_status": execution_status,
        "normalized_spl_available": bool(spl_validation.get("normalized_spl")),
        "execution_eligible": bool(spl_validation.get("execution_eligible") or run_contract.get("spl_execution_eligible")),
        "approved": approved,
        "legacy_spl_validated": bool(run_contract.get("spl_validated")),
        "legacy_validator_status": handoff.get("validator_status"),
        "legacy_validator_status_definition": (
            "execution-promotion verdict on the candidate envelope; not a verdict on the authored SPL"
        ),
    }


def _llm_block(
    *,
    payload: dict[str, Any],
    trace: dict[str, Any],
    candidate_lifecycle: dict[str, Any],
    synthesis: dict[str, Any],
    spl_authoring: dict[str, Any],
) -> dict[str, Any]:
    """Report the LLM per role.

    One `llm_used` boolean cannot describe four roles. A dropped SPL advisory and
    an accepted narration are different facts, and the legacy field -- kept
    verbatim for existing consumers -- answers neither on its own.
    """
    budget = _as_dict(trace.get("llm_turn_budget"))
    interactions = _as_list(trace.get("llm_interactions"))
    records = [
        item
        for item in (interactions or _as_list(trace.get("llm_calls")) or _as_list(budget.get("records")))
        if isinstance(item, dict)
    ]
    roles = [str(item.get("role") or "") for item in records if item.get("role")]
    accepted_roles = []
    for item in records:
        role = str(item.get("role") or "")
        if not role:
            continue
        disposition = item.get("disposition") if isinstance(item.get("disposition"), dict) else {}
        if "accepted" in item or "accepted" in disposition:
            if bool(item.get("accepted") or disposition.get("accepted")):
                accepted_roles.append(role)
            continue
        status = str(item.get("status") or item.get("outcome") or "")
        if status not in {"", "dropped", "failed", "timed_out", "skipped", "not_called"}:
            accepted_roles.append(role)
    intent_status = str(_dig(trace, "query_to_intent", "llm_intent_assist_status") or "")
    spl_authoring_used = bool(candidate_lifecycle["used"])
    synthesis_used = synthesis["synthesis_source"] == "LLM_SYNTHESIS"
    repair_used = bool(candidate_lifecycle["repair_used"])
    contributed = bool(spl_authoring_used or synthesis_used or repair_used)
    return {
        "llm_called_any": bool(records),
        "llm_contributed_to_final_output": contributed,
        "llm_used_in_final_answer": contributed,
        "llm_used_for_intent": intent_status not in {"", "skipped", "disabled"},
        "llm_used_for_spl_authoring": spl_authoring_used,
        "llm_used_for_spl_repair": repair_used,
        "llm_used_for_synthesis": synthesis_used,
        "roles_attempted": sorted(set(roles)),
        "roles_accepted": sorted(set(accepted_roles)),
        # Deliberately NOT named `live_calls`: `debug_summary.llm.live_calls`
        # counts completed hops, and reusing the name for attempts would recreate
        # the ambiguity this block exists to remove.
        "calls_attempted": len(records),
        "calls_completed": len(
            [item for item in records if str(item.get("outcome") or "") == "completed"]
        ),
        "narration_calls": _int_or_none(budget.get("narration_calls")),
        "sidecar_calls": _int_or_none(budget.get("sidecar_calls")),
        "final_spl_authority": spl_authoring["final_spl_authority"],
        "legacy_llm_used": _legacy_llm_used(payload, records),
        "legacy_llm_used_definition": (
            "unchanged: true only when an LLM materially authored the final SPL or synthesis; "
            "an attempted-and-dropped advisory keeps it false"
        ),
    }


def _legacy_llm_used(payload: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    """Reproduce the bundle's legacy `llm_used` verdict, unchanged.

    Echoed here so a reader can see the legacy boolean next to the role-scoped
    fields and confirm they agree rather than guessing which one is stale. The
    definition is deliberately identical to `app.quality.store._llm_used`.
    """
    candidate = _as_dict(payload.get("candidate_spl"))
    validation = _as_dict(payload.get("spl_validation"))
    provider = str(
        candidate.get("selected_candidate_spl_provider")
        or validation.get("selected_candidate_spl_provider")
        or ""
    )
    if not is_deterministic_spl_provider(provider) and llm_used_factual(
        candidate_spl=candidate,
        spl_validation=validation,
        budget_records=records or None,
    ):
        return True
    synthesis = _as_dict(payload.get("synthesis_status"))
    return any(synthesis.get(flag) for flag in ("llm_supported", "llm_fallback_used", "llm_called"))


def _execution_block(
    *,
    payload: dict[str, Any],
    trace: dict[str, Any],
    run_contract: dict[str, Any],
    review_only: dict[str, Any],
) -> dict[str, Any]:
    mcp = _as_dict(trace.get("mcp_execution"))
    execution = _as_dict(payload.get("execution"))
    spl_validation = _as_dict(payload.get("spl_validation"))
    status = str(mcp.get("status") or execution.get("status") or "") or None
    result_count = _int_or_none(mcp.get("result_count"))
    performed = bool(status not in {None, "skipped", "blocked", "not_run"} and mcp.get("selected_mcp_tool"))
    return {
        "execution_requested": bool(review_only["execution_requested_by_user"]),
        "execution_needed_for_answer": bool(run_contract.get("execution_needed_for_answer")),
        "execution_performed": performed,
        "execution_authorized": bool(run_contract.get("execution_authorized")),
        "mcp_status": status,
        "mcp_calls": 1 if performed else 0,
        "mcp_block_reason": mcp.get("block_reason"),
        "mcp_selected_tool": mcp.get("selected_mcp_tool"),
        "splunk_calls": 1 if performed and mcp.get("selected_mcp_server") == "splunk" else 0,
        "live_mcp_called": bool(payload.get("live_mcp_called")),
        "result_count": result_count if result_count is not None else 0,
        "execution_eligible": bool(
            spl_validation.get("execution_eligible") or run_contract.get("spl_execution_eligible")
        ),
        "approved": bool(spl_validation.get("approved")),
        "normalized_spl_available": bool(spl_validation.get("normalized_spl")),
    }


def _hil_block(
    *,
    payload: dict[str, Any],
    trace: dict[str, Any],
    run_contract: dict[str, Any],
    evidence_plan: dict[str, Any],
    source_profile: dict[str, Any],
    review_only: dict[str, Any],
    spl_authoring: dict[str, Any],
) -> dict[str, Any]:
    """Separate a current-turn block from a deferred execution approval.

    A review-only draft that the user asked not to execute is not blocked on the
    analyst: the artifact was delivered. What remains is an execution-time
    requirement. Reporting one `hil_required` for both, with a reason a later
    stage already resolved, is what made the bundle self-contradictory.
    """
    human_review = _as_dict(payload.get("human_review"))
    raised_required = bool(human_review.get("required"))
    raised_reason = human_review.get("reason") if raised_required else None
    raised_kind = human_review.get("review_type") or human_review.get("kind")
    handoff = _as_dict(trace.get("spl_artifact_handoff_summary"))

    # A source-profile clarification is superseded for THIS turn when the final
    # binding summary proves no slot is missing and the artifact was delivered
    # review-only. Any other review kind, and any genuinely missing binding,
    # passes through untouched.
    superseded = bool(
        raised_required
        and str(raised_kind or "") in _SOURCE_PROFILE_REVIEW_KINDS
        and source_profile["all_required_bindings_resolved"]
        and review_only["explicit_do_not_execute"]
        and spl_authoring["spl_artifact_available"]
    )

    if superseded:
        current_required = False
        current_reason = None
        execution_required = True
        execution_reason = (
            "review_only_placeholder_pending_binding"
            if source_profile["slots_resolved_but_withheld_from_review_draft"]
            else str(raised_reason)
        )
    else:
        current_required = raised_required
        current_reason = str(raised_reason) if raised_reason else None
        execution_required = bool(raised_required or not run_contract.get("execution_authorized"))
        execution_reason = str(raised_reason) if raised_reason else None

    return {
        "baseline_hil_required": bool(
            _dig(trace, "query_to_intent", "intent_classification", "requires_hil")
            or evidence_plan.get("requires_hil")
            or evidence_plan.get("needs_hil")
        ),
        "current_turn_hil_required": current_required,
        "current_turn_hil_reason": current_reason,
        "final_hil_reason": current_reason,
        "execution_hil_required": execution_required,
        "execution_hil_reason": execution_reason,
        "artifact_review_required": bool(
            handoff.get("artifact_review_required") or spl_authoring["spl_artifact_available"]
        ),
        "initial_hil_candidate_reason": str(raised_reason) if raised_reason else None,
        "initial_hil_candidate_kind": str(raised_kind) if raised_kind else None,
        "initial_hil_candidate_stage": "spl_source_resolve" if superseded else None,
        "superseded_by_final_resolution": superseded,
        "superseded_by": "source_profile_binding_summary" if superseded else None,
        "legacy_hil_required": bool(human_review) or bool(run_contract.get("effective_hil_required")),
        "legacy_hil_reason": str(raised_reason) if raised_reason else None,
        "run_contract_effective_hil_required": bool(run_contract.get("effective_hil_required")),
        "intent_requires_hil": bool(_dig(trace, "query_to_intent", "intent_classification", "requires_hil")),
        "evidence_plan_requires_hil": bool(evidence_plan.get("requires_hil") or evidence_plan.get("needs_hil")),
    }


def _evidence_plan_classification(evidence_plan: dict[str, Any]) -> dict[str, Any]:
    """Mark catalogue metadata as metadata.

    An `alert_summary`-shaped checklist, a DNS evidence leg and MITRE candidates
    all appear on the plan for this answer mode. None of them were required to
    author a review-only SPL, and the final answer correctly suppresses them --
    but a future reader could not tell that from the plan alone.
    """
    runtime_required = {
        "spl": evidence_plan.get("needs_spl"),
        "rag": evidence_plan.get("needs_rag"),
        "mcp": evidence_plan.get("needs_mcp"),
        "mitre": evidence_plan.get("needs_mitre"),
        "hil": evidence_plan.get("needs_hil"),
        "clarification": evidence_plan.get("needs_clarification"),
    }
    metadata_only = [key for key in _PLANNING_METADATA_KEYS if evidence_plan.get(key)]
    return {
        "runtime_required": runtime_required,
        "planning_metadata_only": metadata_only,
        "planning_metadata_only_flag": True,
        "runtime_required_flag": False,
        "note": (
            "Keys under planning_metadata_only are catalogue projections for the matched "
            "use case. They were not runtime inputs to this answer and must not be read as "
            "evidence the run required."
        ),
    }


def _status_block(
    *,
    payload: dict[str, Any],
    hil: dict[str, Any],
    spl_authoring: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    # The bundle's own `status` lives on the trace-run row, not the response, so
    # this is the response-derived equivalent and is named as such.
    human_review = _as_dict(payload.get("human_review"))
    return {
        "derived_run_status": "human_review" if human_review.get("required") else "completed",
        "artifact_review_required": hil["artifact_review_required"],
        "execution_approval_required_if_requested": hil["execution_hil_required"],
        "current_turn_blocked_for_hil": hil["current_turn_hil_required"],
        "artifact_delivered": spl_authoring["spl_artifact_available"],
        "execution_performed": execution["execution_performed"],
    }
