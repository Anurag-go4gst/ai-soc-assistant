"""STANDARD reviewer debug export — compact projection over a forensic bundle.

Default ``/debug/traces/{id}/bundle`` stays the lossless forensic contract.
``detail=reviewer`` returns this projection. Nothing here is runtime authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.chat.llm_interaction_trace import (
    SYNTHESIS_ROLES,
    compact_llm_call_index,
    count_interactions_by_role,
    hydrate_llm_interaction,
    snapshot_llm_interactions,
)
from app.chat.trace_artifacts import (
    artifact_ref,
    build_artifact_index,
    llm_call_ref,
)
from app.chat.trace_effective_state import build_effective_state_projection

SCHEMA_VERSION = "reviewer_trace_v2"
_PREVIEW_LIMIT = 240
_HEAVY_EVENT_DROP_KEYS = frozenset(
    {
        "debug_summary",
        "control_plane_trace",
        "evidence_plan",
        "resource_plan",
        "final_output",
        "effective_state",
        "message",
        "analyst_summary",
        "candidate_spl",
        "utility_spl_draft_trace",
        "request",
        "response",
        "system_prompt",
        "user_prompt",
        "raw_text",
        "parsed_payload",
        "forensic",
    }
)


def assemble_forensic_bundle(
    *,
    trace_id: str,
    run: dict[str, Any] | None,
    events: list[dict[str, Any]] | None,
    event_truncated: bool = False,
    event_limit: int | None = None,
    decode_error_count: int = 0,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the backward-compatible forensic bundle with canonical ES filled."""
    run = dict(run or {})
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    debug_summary = metadata.get("debug_summary") if isinstance(metadata.get("debug_summary"), dict) else None
    canonical_es = _canonical_effective_state(metadata=metadata, debug_summary=debug_summary, payload=payload)
    llm_interactions = _canonical_llm_interactions(metadata=metadata, events=events or [])
    explainability = {
        "effective_state": canonical_es,
        "debug_summary": debug_summary,
        "control_plane_trace": metadata.get("control_plane_trace"),
        "governance_trace": metadata.get("governance_trace"),
        "lineage_summary": metadata.get("lineage_summary"),
        "llm_sidecars": metadata.get("llm_sidecars"),
        "llm_interactions": llm_interactions,
        "final_output": metadata.get("final_output"),
    }
    bundle = {
        "trace_id": trace_id,
        "schema_version": "forensic_trace_v1",
        "run": run,
        "timeline": list(events or []),
        "explainability": explainability,
        "turn_id": metadata.get("turn_id") or run.get("turn_id"),
        "event_truncated": bool(event_truncated),
        "event_limit": event_limit,
        "decode_error_count": int(decode_error_count or 0),
    }
    bundle["artifacts"] = build_artifact_index(bundle)
    return bundle


def build_reviewer_trace(forensic_bundle: dict[str, Any]) -> dict[str, Any]:
    """Compact STANDARD export. Heavy objects are referenced, not copied."""
    bundle = forensic_bundle if isinstance(forensic_bundle, dict) else {}
    explain = bundle.get("explainability") if isinstance(bundle.get("explainability"), dict) else {}
    run = bundle.get("run") if isinstance(bundle.get("run"), dict) else {}
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    effective = explain.get("effective_state") if isinstance(explain.get("effective_state"), dict) else {}
    if effective.get("schema_version") != "trace_effective_state_v1":
        effective = _canonical_effective_state(metadata=metadata, debug_summary=explain.get("debug_summary"))
    llm_interactions = explain.get("llm_interactions") if isinstance(explain.get("llm_interactions"), list) else []
    if not llm_interactions:
        llm_interactions = _canonical_llm_interactions(metadata=metadata, events=bundle.get("timeline") or [])
    compact_llm = compact_llm_call_index(llm_interactions)
    counts = count_interactions_by_role(compact_llm or llm_interactions)
    artifacts = dict(bundle.get("artifacts") or build_artifact_index(bundle))
    artifacts.setdefault("full_debug_bundle_ref", artifact_ref("full_debug_bundle"))
    for item in compact_llm:
        if item.get("interaction_id") and not item.get("forensic_ref"):
            item["forensic_ref"] = llm_call_ref(str(item["interaction_id"]))
    hil = _hil_projection(effective)
    validation = effective.get("validation") if isinstance(effective.get("validation"), dict) else {}
    execution = effective.get("execution") if isinstance(effective.get("execution"), dict) else {}
    rag = effective.get("rag") if isinstance(effective.get("rag"), dict) else {}
    evidence_plan_class = (
        effective.get("evidence_plan_classification")
        if isinstance(effective.get("evidence_plan_classification"), dict)
        else effective.get("evidence_plan")
        if isinstance(effective.get("evidence_plan"), dict)
        else {}
    )
    review_decision = _review_decision(effective=effective, hil=hil, execution=execution)
    effective_ref = {"$ref": artifact_ref("effective_state")} if effective else None
    return {
        "trace_id": bundle.get("trace_id") or run.get("trace_id"),
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "legacy_run_status": run.get("status"),
            "review_outcome": review_decision["run_outcome"],
            "answer_mode": effective.get("answer_mode") or run.get("answer_mode") or metadata.get("answer_mode"),
            "use_case_id": run.get("use_case_id") or metadata.get("use_case_id"),
            "duration_ms": run.get("duration_ms"),
            "selected_skill": run.get("selected_skill") or metadata.get("selected_skill"),
        },
        "review_decision": review_decision,
        "effective_state": effective_ref,
        "spl": _spl_projection(effective, validation, execution),
        "llm": _llm_projection(effective, compact_llm, counts),
        "synthesis": _synthesis_projection(effective, compact_llm),
        "enrichment": _enrichment_projection(effective, rag),
        "execution": _execution_projection(effective, execution),
        "evidence": _evidence_projection(effective, execution),
        "source_binding": _source_binding_projection(effective),
        "hil": hil,
        "connectors": _connector_projection(effective, evidence_plan_class, execution, counts),
        "timeline": [
            compact_timeline_event(event, effective=effective) for event in bundle.get("timeline") or [] if isinstance(event, dict)
        ],
        "artifacts": artifacts,
        "explainability": {
            "effective_state": effective_ref,
            "final_output": _reviewer_final_output(explain.get("final_output"), hil=hil, effective=effective),
            "debug_summary": None,
            "control_plane_trace": None,
        },
        "turn_id": bundle.get("turn_id") or run.get("turn_id"),
        "event_truncated": bundle.get("event_truncated"),
        "event_limit": bundle.get("event_limit"),
    }


def compact_timeline_event(event: dict[str, Any], *, effective: dict[str, Any] | None = None) -> dict[str, Any]:
    body = event.get("event") if isinstance(event.get("event"), dict) else {}
    kind = str(event.get("kind") or "")
    # Live telemetry often stamps step_name on the inner body, not the envelope.
    step_name = str(event.get("step_name") or body.get("step_name") or "")
    compact_body = {key: value for key, value in body.items() if key not in _HEAVY_EVENT_DROP_KEYS}
    if "query" in compact_body:
        original_query = compact_body.pop("query")
        compact_body["question_preview"] = _preview(original_query)
        if isinstance(original_query, str) and original_query.strip():
            compact_body["question_hash"] = hashlib.sha256(original_query.encode()).hexdigest()
    if "query_preview" in compact_body:
        compact_body["query_preview"] = _preview(compact_body.get("query_preview"))
    if kind == "rag_retrieval":
        compact_body.update(classify_rag_event(body, effective=effective))
    if kind == "llm_call":
        interaction_id = str(body.get("interaction_id") or "")
        compact_body = {
            "interaction_id": interaction_id or None,
            "role": body.get("role"),
            "stage": body.get("stage"),
            "provider_label": body.get("provider_label"),
            "model": body.get("model"),
            "outcome": body.get("outcome") or body.get("status"),
            "latency_ms": body.get("latency_ms"),
            "prompt_hash": body.get("prompt_hash"),
            "response_hash": body.get("response_hash"),
            "reject_reason": body.get("reject_reason"),
            "accepted": body.get("accepted"),
            "forensic_ref": llm_call_ref(interaction_id) if interaction_id else None,
        }
    if kind == "step" and step_name in {"node.finalize_response", "finalize_response"}:
        compact_body = {
            "final_answer_ref": artifact_ref("final_answer"),
            "status": event.get("status") or body.get("status"),
            "answer_mode": body.get("answer_mode"),
            "message_preview": _preview(body.get("message_preview") or body.get("message")),
            "hil_required_legacy": body.get("hil_required"),
            "current_turn_hil_required": (effective or {}).get("hil", {}).get("current_turn_hil_required")
            if isinstance((effective or {}).get("hil"), dict)
            else None,
        }
    fact_kind = compact_body.get("fact_kind") or compact_body.get("kind")
    kinds = compact_body.get("kinds")
    executed_in_kinds = isinstance(kinds, list) and "executed_evidence" in kinds
    if (
        fact_kind == "executed_evidence"
        or compact_body.get("legacy_fact_kind") == "executed_evidence"
        or executed_in_kinds
    ):
        compact_body.update(
            classify_fact_kind(
                {**compact_body, "fact_kind": fact_kind or "executed_evidence"},
                effective=effective,
            )
        )
    return {
        "kind": kind,
        "created_at": event.get("created_at"),
        "step_name": step_name or event.get("step_name"),
        "status": event.get("status"),
        "event": compact_body,
    }


def classify_rag_event(body: dict[str, Any], *, effective: dict[str, Any] | None = None) -> dict[str, Any]:
    origin = str(body.get("evidence_origin") or "")
    stage = str(body.get("retrieval_workflow_stage") or body.get("workflow_stage") or "")
    rag = (effective or {}).get("rag") if isinstance((effective or {}).get("rag"), dict) else {}
    skipped_utility = origin == "rag_skipped_for_spl_utility_authoring"
    source_hint = stage == "spl_source_resolve" or (
        origin in {"stub_rag", "governed_soc_kb_retrieval"} and rag.get("runtime_rag_used") is False
    )
    if skipped_utility:
        runtime_rag = False
        enrichment = False
        purpose = "skipped_spl_utility_authoring"
    elif source_hint or rag.get("enrichment_lookup_used"):
        runtime_rag = False
        enrichment = True
        purpose = str(rag.get("enrichment_purpose") or "source_profile_hint")
    else:
        runtime_rag = bool(rag.get("runtime_rag_used")) if rag else origin not in {"", "skipped"}
        enrichment = False
        purpose = "runtime_rag" if runtime_rag else "unknown"
    return {
        "runtime_rag": runtime_rag,
        "enrichment": enrichment,
        "purpose": purpose,
        "authoritative_for_live_findings": False,
        "retrieval_workflow_stage": stage or rag.get("retrieval_workflow_stage"),
        "evidence_origin": origin or None,
    }


def classify_fact_kind(body: dict[str, Any], *, effective: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence_class = str(body.get("evidence_class") or _dig(body, "provenance", "evidence_class") or "")
    live = bool((effective or {}).get("execution", {}).get("execution_performed")) if isinstance((effective or {}).get("execution"), dict) else False
    if evidence_class in {"mcp_search", "mcp", "execution", "splunk_mcp"} and live:
        effective_kind = "executed_evidence"
    elif evidence_class in {"rag", "knowledge", "kb", "source"}:
        effective_kind = "source_evidence" if evidence_class != "knowledge" else "knowledge_evidence"
    else:
        effective_kind = "source_evidence"
    return {
        "legacy_fact_kind": body.get("fact_kind") or body.get("kind") or "executed_evidence",
        "effective_fact_kind": effective_kind,
        "live_execution": live,
    }


def reviewer_has_duplicated_heavy_object(reviewer: dict[str, Any]) -> list[str]:
    """Return names of heavy objects that appear more than once in the export."""
    serialized = _stable_dump(reviewer)
    duplicates: list[str] = []
    checks = (
        ("debug_summary", '"schema_version": "debug_summary"' in serialized or serialized.count('"routing"') > 3),
        ("control_plane_trace", serialized.count('"query_to_intent"') > 1),
        ("effective_state", serialized.count('"schema_version": "trace_effective_state_v1"') > 1),
    )
    # Path-based: nested copies of the same canonical blocks.
    if _count_key(reviewer, "debug_summary") > 0 and reviewer.get("explainability", {}).get("debug_summary"):
        duplicates.append("debug_summary")
    if _count_key(reviewer, "control_plane_trace") > 1:
        duplicates.append("control_plane_trace")
    if _nested_effective_state_copies(reviewer) > 1:
        duplicates.append("effective_state")
    for name, flagged in checks:
        if flagged and name not in duplicates and name == "debug_summary":
            continue
    return duplicates


def _canonical_effective_state(
    *,
    metadata: dict[str, Any],
    debug_summary: Any = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _real(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict) and value.get("schema_version") == "trace_effective_state_v1":
            return value
        return None

    top = _real(metadata.get("effective_state"))
    nested = _real(debug_summary.get("effective_state") if isinstance(debug_summary, dict) else None)
    if top:
        return top
    if nested:
        return nested
    if isinstance(payload, dict) and payload:
        return build_effective_state_projection(payload)
    return {}


def _canonical_llm_interactions(*, metadata: dict[str, Any], events: list[Any]) -> list[dict[str, Any]]:
    from_events: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict) or event.get("kind") != "llm_call":
            continue
        body = event.get("event") if isinstance(event.get("event"), dict) else {}
        if body.get("schema_version") == "llm_interaction_v1" or body.get("forensic"):
            from_events.append(hydrate_llm_interaction(body))
    if from_events:
        return from_events
    stored = metadata.get("llm_interactions")
    if isinstance(stored, list) and stored:
        return [hydrate_llm_interaction(item) for item in stored if isinstance(item, dict)]
    live = snapshot_llm_interactions()
    return live if live else []


def _hil_projection(effective: dict[str, Any]) -> dict[str, Any]:
    hil = effective.get("hil") if isinstance(effective.get("hil"), dict) else {}
    superseded = bool(hil.get("superseded_by_final_resolution"))
    current_reason = hil.get("current_turn_hil_reason")
    if superseded and current_reason == hil.get("initial_hil_candidate_reason"):
        current_reason = None
    baseline = hil.get("baseline_hil_required")
    if baseline is None:
        baseline = bool(hil.get("intent_requires_hil") or hil.get("evidence_plan_requires_hil"))
    return {
        "baseline_hil_required": bool(baseline),
        "current_turn_hil_required": bool(hil.get("current_turn_hil_required")),
        "current_turn_hil_reason": current_reason,
        "artifact_review_required": bool(hil.get("artifact_review_required")),
        "execution_hil_required_if_requested": bool(hil.get("execution_hil_required")),
        "execution_hil_reason": hil.get("execution_hil_reason"),
        "superseded_by_final_resolution": superseded,
    }


def _review_decision(
    *,
    effective: dict[str, Any],
    hil: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Reviewer-only outcome. Not runtime HIL or execution authority."""
    current_turn = bool(hil.get("current_turn_hil_required"))
    performed = bool(execution.get("execution_performed"))
    authorized = bool(execution.get("execution_authorized"))
    review_only = str(effective.get("answer_mode") or "") in {
        "spl_utility_authoring",
        "spl_review_only",
        "review_only",
    } or bool(hil.get("artifact_review_required"))
    if performed:
        run_outcome = "completed_with_execution"
    elif current_turn:
        run_outcome = "blocked_for_hil"
    elif review_only:
        run_outcome = "completed_review_only"
    else:
        run_outcome = "completed"
    return {
        "run_outcome": run_outcome,
        "artifact_ready_for_review": bool(hil.get("artifact_review_required")) or review_only,
        "current_turn_requires_user_input": current_turn,
        "current_turn_blocked_for_hil": current_turn,
        "execution_permitted": bool(authorized or performed),
        "execution_requires_approval_if_requested": bool(hil.get("execution_hil_required_if_requested")),
        "reason": (
            "Review-only SPL artifact delivered; live execution was neither requested nor authorised."
            if run_outcome == "completed_review_only"
            else None
        ),
    }


def _spl_projection(
    effective: dict[str, Any],
    validation: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    authoring = effective.get("spl_authoring") if isinstance(effective.get("spl_authoring"), dict) else {}
    llm_status = str(validation.get("llm_candidate_validation_status") or "")
    if llm_status in {"failed", "rejected"}:
        llm_candidate_status = "rejected"
    elif llm_status in {"passed", "accepted"}:
        llm_candidate_status = "accepted"
    elif llm_status:
        llm_candidate_status = llm_status
    else:
        llm_candidate_status = "not_run"
    execution_eligible = validation.get("execution_eligible")
    if execution_eligible is None:
        execution_eligible = authoring.get("execution_eligible")
    authoring_status = validation.get("authoring_fidelity_status") or "unknown"
    safety = "passed" if authoring_status == "passed" and not execution_eligible else authoring_status
    return {
        "authoring_fidelity_status": authoring_status,
        "llm_candidate_status": llm_candidate_status,
        "llm_candidate_reason": (validation.get("llm_candidate_validation_reasons") or [None])[0]
        if validation.get("llm_candidate_validation_reasons")
        else None,
        "llm_candidate_validation_status": llm_status or None,
        "llm_candidate_reject_reason": (validation.get("llm_candidate_validation_reasons") or [None])[0]
        if validation.get("llm_candidate_validation_reasons")
        else None,
        "llm_candidate_validation_reasons": validation.get("llm_candidate_validation_reasons") or [],
        "candidate_spl_validation_status": validation.get("candidate_spl_validation_status"),
        "execution_promotion_status": validation.get("execution_validation_status"),
        "execution_validation_status": validation.get("execution_validation_status"),
        "candidate_execution_eligible": bool(execution_eligible),
        "execution_eligible": bool(execution_eligible),
        "execution_performed": bool(execution.get("execution_performed")),
        "final_answer_safety_status": safety,
        "normalized_spl_available": validation.get("normalized_spl_available"),
        "final_spl_hash": authoring.get("final_spl_hash"),
        "final_raw_spl_source": authoring.get("final_raw_spl_source") or validation.get("final_spl_source"),
    }


def _llm_projection(
    effective: dict[str, Any],
    compact_llm: list[dict[str, Any]],
    counts: dict[str, Any],
) -> dict[str, Any]:
    llm = effective.get("llm") if isinstance(effective.get("llm"), dict) else {}
    used_in_final = counts.get("llm_used_in_final_answer") if compact_llm else llm.get("llm_used_in_final_answer")
    if used_in_final is None:
        used_in_final = llm.get("llm_contributed_to_final_output")
    rejected = list(counts.get("rejected_roles") or counts.get("dropped_llm_roles") or [])
    return {
        "interactions_attempted": counts.get("interactions_attempted", counts.get("total_attempts")),
        "interactions_completed": counts.get("interactions_completed"),
        "interactions_accepted": counts.get("interactions_accepted"),
        "interactions_contributing_to_final_output": counts.get("interactions_contributing_to_final_output"),
        "rejected_roles": rejected,
        "accepted_llm_roles": list(counts.get("accepted_llm_roles") or [])
        if "accepted_llm_roles" in counts
        else list(llm.get("roles_accepted") or []),
        "llm_used_in_final_answer": bool(used_in_final),
        "llm_contributed_to_final_output": bool(llm.get("llm_contributed_to_final_output")),
        "dropped_llm_roles": counts.get("dropped_llm_roles") or rejected,
        "llm_sidecar_attempt_count": counts.get("llm_sidecar_attempt_count"),
        "llm_sidecar_completed_count": counts.get("llm_sidecar_completed_count"),
        "llm_synthesis_attempt_count": counts.get("llm_synthesis_attempt_count"),
        "llm_synthesis_completed_count": counts.get("llm_synthesis_completed_count"),
        "llm_repair_attempt_count": counts.get("llm_repair_attempt_count"),
        "spl_advisory_attempt_count": counts.get("spl_advisory_attempt_count"),
        "legacy_llm_used": llm.get("legacy_llm_used"),
        "legacy_llm_used_definition": llm.get("legacy_llm_used_definition"),
        "interactions": compact_llm,
    }


def _synthesis_projection(effective: dict[str, Any], compact_llm: list[dict[str, Any]]) -> dict[str, Any]:
    synthesis = effective.get("synthesis") if isinstance(effective.get("synthesis"), dict) else {}
    synth_calls = [item for item in compact_llm if str(item.get("role") or "") in SYNTHESIS_ROLES]
    return {
        "synthesis_source": synthesis.get("synthesis_source"),
        "synthesis_status": synthesis.get("synthesis_status"),
        "llm_call_attempted": bool(synthesis.get("synthesis_attempted") or synth_calls),
        "fallback_reason": (synthesis.get("synthesis_fallback_reason") or [None])[0]
        if isinstance(synthesis.get("synthesis_fallback_reason"), list)
        else synthesis.get("synthesis_fallback_reason"),
        "latency_ms": synthesis.get("synthesis_latency_ms"),
        "interaction_refs": [
            {
                "interaction_id": item.get("interaction_id"),
                "role": item.get("role"),
                "forensic_ref": item.get("forensic_ref"),
                "reject_reason": item.get("reject_reason"),
                "accepted": item.get("accepted"),
            }
            for item in synth_calls
        ],
    }


def _enrichment_projection(effective: dict[str, Any], rag: dict[str, Any]) -> dict[str, Any]:
    return {
        "runtime_rag_used": bool(rag.get("runtime_rag_used")),
        "optional_enrichment_used": bool(rag.get("enrichment_lookup_used")),
        "enrichment_type": rag.get("enrichment_purpose") or rag.get("enrichment_type"),
        "enrichment_stage": rag.get("retrieval_workflow_stage"),
        "enrichment_result_count": rag.get("retrieval_result_count") or rag.get("result_count"),
        "allowed_to_ground_final_analytic_answer": bool(rag.get("allowed_to_ground_final_analytic_answer")),
    }


def _execution_projection(effective: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    evidence = effective.get("evidence") if isinstance(effective.get("evidence"), dict) else {}
    return {
        "execution_requested": bool(execution.get("execution_requested")),
        "execution_performed": bool(execution.get("execution_performed")),
        "execution_authorized": bool(execution.get("execution_authorized")),
        "mcp_calls": execution.get("mcp_calls") or 0,
        "splunk_calls": execution.get("splunk_calls") or 0,
        "live_execution_evidence_available": bool(evidence.get("live_execution_evidence_available")),
        "execution_eligible": bool(execution.get("execution_eligible")),
    }


def _evidence_projection(effective: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    evidence = effective.get("evidence") if isinstance(effective.get("evidence"), dict) else {}
    executed = evidence.get("executed_evidence") if isinstance(evidence.get("executed_evidence"), dict) else {}
    artifact = evidence.get("spl_artifact") if isinstance(evidence.get("spl_artifact"), dict) else {}
    return {
        "spl_artifact_available": bool(evidence.get("artifact_evidence_available")),
        "spl_artifact_status": artifact.get("status"),
        "live_execution_evidence_available": bool(evidence.get("live_execution_evidence_available")),
        "executed_evidence_status": executed.get("status"),
        "executed_evidence_reason": executed.get("reason"),
        "execution_performed": bool(execution.get("execution_performed")),
        "evidence_plan_ref": artifact_ref("evidence_plan"),
        "resource_plan_ref": artifact_ref("resource_plan"),
    }


def _source_binding_projection(effective: dict[str, Any]) -> dict[str, Any]:
    """Runtime resolution vs review-draft display. Never copies internal index values."""
    profile = effective.get("source_profile") if isinstance(effective.get("source_profile"), dict) else {}
    slots_in = profile.get("slots") if isinstance(profile.get("slots"), dict) else {}
    slots_out: dict[str, Any] = {}
    for name, slot in slots_in.items():
        if not isinstance(slot, dict):
            continue
        display = slot.get("display_value")
        placeholder = _is_display_placeholder(display)
        slots_out[str(name)] = {
            "runtime_binding_resolved": bool(slot.get("resolved")),
            "runtime_value_source": slot.get("resolution_source"),
            "review_draft_display_value": display,
            "review_draft_display_reason": slot.get("withholding_reason") if placeholder else None,
            "intentional_display_placeholder": bool(
                placeholder and slot.get("withholding_reason") == "review_only_placeholder_policy"
            ),
            "exposed_in_review_draft": bool(slot.get("exposed_in_review_draft")),
        }
    index = slots_out.get("index") if isinstance(slots_out.get("index"), dict) else {}
    return {
        "runtime_binding_resolved": bool(profile.get("all_required_bindings_resolved")),
        "runtime_value_source": index.get("runtime_value_source"),
        "review_draft_display_value": index.get("review_draft_display_value"),
        "review_draft_display_reason": index.get("review_draft_display_reason"),
        "intentional_display_placeholder": bool(index.get("intentional_display_placeholder")),
        "slots": slots_out,
    }


def _is_display_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return text.startswith("<") and text.endswith(">")


def _connector_projection(
    effective: dict[str, Any],
    evidence_plan_class: dict[str, Any],
    execution: dict[str, Any],
    counts: dict[str, Any],
) -> dict[str, Any]:
    runtime = evidence_plan_class.get("runtime_required") if isinstance(evidence_plan_class.get("runtime_required"), dict) else {}
    plan = effective.get("evidence_plan") if isinstance(effective.get("evidence_plan"), dict) else evidence_plan_class
    required = plan.get("required_connectors") or plan.get("potential_connectors")
    resource = plan.get("resource_decisions") if isinstance(plan.get("resource_decisions"), dict) else {}
    connectors = required or resource.get("required_connectors") or plan.get("connectors")
    if isinstance(connectors, list) and connectors:
        potential = [str(item) for item in connectors]
    else:
        # Planning often lists llm+mcp even when neither is runtime-required.
        potential = ["llm", "mcp"]
    llm_count = int(counts.get("interactions_attempted") or counts.get("total_attempts") or 0)
    mcp_required = bool(runtime.get("mcp"))
    mcp_calls = int(execution.get("mcp_calls") or 0)
    splunk_calls = int(execution.get("splunk_calls") or 0)
    return {
        "potential_connectors": potential,
        "runtime_required_connectors": {
            "llm": False,
            "mcp": mcp_required,
            "splunk": False,
        },
        "actual_connector_usage": {
            "llm_interactions": llm_count,
            "llm_attempted": llm_count > 0,
            "llm_calls": llm_count,
            "mcp_calls": mcp_calls,
            "splunk_calls": splunk_calls,
        },
        "mcp_required_this_turn": mcp_required,
        "mcp_executed": mcp_calls > 0,
        "runtime_requirements": {
            "spl": bool(runtime.get("spl")),
            "rag": bool(runtime.get("rag")),
            "mcp": mcp_required,
            "hil": bool(runtime.get("hil")),
            "mitre": bool(runtime.get("mitre")),
        },
    }


def _reviewer_final_output(final_output: Any, *, hil: dict[str, Any], effective: dict[str, Any]) -> dict[str, Any]:
    source = final_output if isinstance(final_output, dict) else {}
    return {
        "final_answer_ref": artifact_ref("final_answer"),
        "answer_preview": _preview(source.get("message") or source.get("analyst_summary")),
        "answer_mode": source.get("answer_mode") or effective.get("answer_mode"),
        "selected_skill": source.get("selected_skill"),
        "current_turn_hil_required": hil.get("current_turn_hil_required"),
        "artifact_review_required": hil.get("artifact_review_required"),
        "legacy_hil_required": source.get("hil_required"),
        "legacy_hil_reason": source.get("hil_reason"),
    }


def _preview(text: Any, *, limit: int = _PREVIEW_LIMIT) -> str | None:
    if not isinstance(text, str):
        return None
    collapsed = " ".join(text.split()).strip()
    if not collapsed:
        return None
    if len(collapsed) > limit:
        return collapsed[: limit - 1].rstrip() + "…"
    return collapsed


def _dig(payload: dict[str, Any], *keys: str) -> Any:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _count_key(value: Any, key: str) -> int:
    if isinstance(value, dict):
        return int(key in value and value.get(key) not in (None, {})) + sum(_count_key(v, key) for v in value.values())
    if isinstance(value, list):
        return sum(_count_key(item, key) for item in value)
    return 0


def _nested_effective_state_copies(reviewer: dict[str, Any]) -> int:
    serialized = _stable_dump(reviewer)
    return serialized.count('"schema_version": "trace_effective_state_v1"')


def _stable_dump(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)
