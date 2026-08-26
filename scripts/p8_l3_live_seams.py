"""P8 L3-2 — live row execution against real production seams.

Eval harness only. Does not change prompts, models, thresholds, or bank rows.
MCP execution stays off. Blocked reasoners are never invoked.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
TECHNIQUE_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
HEAD_100_RE = re.compile(r"\|\s*head\s+100\b", re.I)

INFRA_RETRY_MARKERS = (
    "ConnectionReset",
    "URLError",
    "TimeoutError",
    "timed out",
    "Connection refused",
    "RemoteDisconnected",
)

# Frozen 1.2.0-candidate stable-prefix hashes. Binding MATCH requires these plus
# the provider request system message hashing to the selected instruction.
EXPECTED_CANDIDATE_PREFIX_HASHES = {
    "semantic_t4": "6e897303f7401d0a303e3a87fe683eaa538c605435bb80a8878bfdebbefc844b",
    "spl_advisory_generator": "42ede55dab7e163ff4281c6b7c7d5aa7f6ebfb50aa3e0885a382e08290338874",
    "investigation_planner": "ff1a47c929fc11ae0cdab02b22c6273ec180e744935d2e113377d1ee3d5fb1c4",
}
_ROLE_ALIASES = {"spl_generation": "spl_advisory_generator"}


def empty_row_result(row: dict[str, Any], **over: Any) -> dict[str, Any]:
    base = {
        "case_id": row["row_id"],
        "category": row.get("category"),
        "role": row.get("role_id"),
        "seam": row.get("seam"),
        "query": row.get("query"),
        "model": None,
        "latency_ms": 0,
        "llm_called": False,
        "llm_response_received": False,
        "llm_accepted": False,
        "llm_used": False,
        "fallback_used": False,
        "structured_output_valid": None,
        "deterministic_validator_result": None,
        "semantic_correctness": None,
        "authority_correctness": True,
        "evidence_truth": True,
        "final_result": "NOT_RUN",
        "failure_class": None,
        "t4_attempted": None,
        "t4_accepted": None,
        "t4_rejected_by_validator": None,
        "t4_fallback": None,
        "t4_semantic_success": None,
        "spl_losses": [],
        "authority_violations": [],
        "evidence_hallucinations": [],
        "notes": [],
        "infra_retry_used": False,
        "eval_arm": None,
        "prompt_id": None,
        "prompt_version": None,
        "prompt_hash": None,
        "prompt_status": None,
        "request_system_prompt_sha256": None,
        "selected_instruction_sha256": None,
        "selected_template_id": None,
        "selected_template_version": None,
        "request_matches_selected_instruction": None,
        "selected_matches_expected_prefix": None,
        "binding_match": None,
    }
    identity = _prompt_identity(row.get("role_id"))
    base.update(identity)
    base.update(over)
    return base


def _prompt_identity(role_id: str | None) -> dict[str, Any]:
    from app.llm.policy.candidates import candidate_for, candidate_stable_prefix_hash
    from app.llm.policy.eval_arm import prompt_eval_arm
    from app.llm.policy.evaluation import contract_for_role

    arm = prompt_eval_arm()
    identity: dict[str, Any] = {
        "eval_arm": arm,
        "prompt_id": None,
        "prompt_version": None,
        "prompt_hash": None,
        "prompt_status": None,
    }
    if not role_id:
        return identity
    mapped = _ROLE_ALIASES.get(role_id, role_id)
    if arm == "candidate":
        cand = candidate_for(mapped)
        if cand is not None:
            identity.update(
                {
                    "prompt_id": cand.template_id,
                    "prompt_version": cand.version,
                    "prompt_hash": candidate_stable_prefix_hash(mapped),
                    "prompt_status": cand.status,
                }
            )
            return identity
    try:
        contract = contract_for_role(mapped)
    except KeyError:
        return identity
    identity.update(
        {
            "prompt_id": contract.active.template_id,
            "prompt_version": contract.active.version,
            "prompt_hash": contract.active.stable_prefix_hash,
            "prompt_status": "ACTIVE",
        }
    )
    return identity


def _one_infra_retry(fn, row: dict[str, Any]) -> dict[str, Any]:
    try:
        return fn(row)
    except Exception as exc:  # noqa: BLE001
        text = f"{type(exc).__name__}: {exc}"
        if not any(marker.lower() in text.lower() for marker in INFRA_RETRY_MARKERS):
            result = empty_row_result(
                row,
                final_result="FAIL",
                failure_class="EVAL_HARNESS_DEFECT",
                notes=[text],
            )
            return result
        try:
            retried = fn(row)
            retried["infra_retry_used"] = True
            retried.setdefault("notes", []).append(f"infra_retry_after:{text}")
            return retried
        except Exception as exc2:  # noqa: BLE001
            return empty_row_result(
                row,
                final_result="FAIL",
                failure_class="MODEL_TIMEOUT",
                notes=[text, f"{type(exc2).__name__}: {exc2}"],
                infra_retry_used=True,
            )


def _t4_contract(query: str):
    from app.chat.intent_classifier import build_query_to_intent
    from app.chat.resolved_query_builder import build_resolved_query_contract
    from app.query_understanding.parser import understand_query

    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    return build_resolved_query_contract(
        query=query,
        query_understanding=understanding,
        qualification_tier="T4",
        qualification_source="p8_l3_2",
        query_to_intent=q2i,
    )


def run_t4_row(row: dict[str, Any], *, model: str) -> dict[str, Any]:
    from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic

    query = str(row.get("query") or "")
    started = time.monotonic()
    base = _t4_contract(query)
    enriched = maybe_enrich_t4_semantic(base, query=query)
    latency_ms = int((time.monotonic() - started) * 1000)
    trace = (enriched.provenance or {}).get("semantic_t4") or {}
    invoked = bool(trace.get("invoked"))
    accepted = bool(trace.get("accepted"))
    rejected = list(trace.get("rejected_reasons") or [])
    fallback = bool(trace.get("fallback") or trace.get("degradation"))
    timed_out = bool(trace.get("timed_out"))
    failure_kind = trace.get("failure_kind")

    goal = (enriched.normalized_goal or "").lower()
    hyps = " ".join(enriched.competing_hypotheses or []).lower()
    constraints_hit: list[bool] = []
    notes: list[str] = []
    row_id = row["row_id"]
    if row_id == "L3.T4.01":
        constraints_hit.append(any(tok in goal for tok in ("lateral", "sideways", "east-west", "movement")))
        constraints_hit.append(("benign" in hyps and "malicious" in hyps) or len(enriched.competing_hypotheses) >= 2)
        notes.append(f"normalized_goal={enriched.normalized_goal!r}")
    elif row_id == "L3.T4.02":
        constraints_hit.append(len(enriched.competing_hypotheses) >= 2 or ("benign" in hyps and "malicious" in hyps))
        constraints_hit.append(bool(enriched.evidence_requirements) and not any(
            word in " ".join(enriched.evidence_requirements).lower()
            for word in ("confirmed", "proved", "attacker was")
        ))
    elif row_id == "L3.T4.03":
        constraints_hit.append(bool(enriched.clarification_required) or enriched.ambiguity_state == "clarification_required")
        invented = any(tok in goal for tok in ("incident-id", "ticket-", "alert-")) and "last week" in goal
        constraints_hit.append(not invented)
    elif row_id == "L3.T4.04":
        constraints_hit.append(any(tok in goal for tok in ("dga", "algorithm", "domain generation", "nxdomain", "dns")))
        caps = " ".join(enriched.required_capabilities or []).lower()
        constraints_hit.append(any(tok in caps for tok in ("spl", "search", "log")))
    else:
        constraints_hit.append(accepted)

    semantic = (sum(constraints_hit) / len(constraints_hit)) if constraints_hit else 0.0
    schema_valid = "schema_invalid" not in rejected and "t4_semantic_invalid_response" not in rejected
    if invoked and not accepted and any("invalid" in str(item) for item in rejected):
        schema_valid = False

    authority_violations: list[str] = []
    if "selected_skill" in (enriched.model_dump()):
        pass
    locked_ok = base.intent_family == enriched.intent_family and base.answer_goal == enriched.answer_goal
    if not locked_ok:
        authority_violations.append("locked_deterministic_field_changed")

    failure_class = None
    if timed_out or failure_kind in {"timeout", "provider_unavailable"}:
        failure_class = "MODEL_TIMEOUT" if timed_out else "MODEL_TIMEOUT"
        if failure_kind == "provider_unavailable":
            failure_class = "MODEL_TIMEOUT"
    elif invoked and not schema_valid:
        failure_class = "MODEL_STRUCTURED_OUTPUT_FAILURE"
    elif invoked and not accepted:
        failure_class = "DETERMINISTIC_VALIDATOR_REJECTION"
    elif fallback and semantic < 1.0:
        failure_class = "FALLBACK_RESCUE"
    elif semantic < 1.0:
        failure_class = "MODEL_SEMANTIC_FAILURE"

    llm_used = invoked and accepted and not fallback
    product_ok = semantic >= 1.0 and not authority_violations
    if invoked and not accepted:
        llm_used = False
        if product_ok:
            final = "PRODUCT_SUCCESS_MODEL_FAILURE"
            failure_class = failure_class or "DETERMINISTIC_VALIDATOR_REJECTION"
        else:
            final = "FAIL"
            failure_class = failure_class or "DETERMINISTIC_VALIDATOR_REJECTION"
    elif fallback and product_ok:
        final = "PRODUCT_SUCCESS_MODEL_FAILURE"
        failure_class = failure_class or "FALLBACK_RESCUE"
    elif product_ok and llm_used:
        final = "PASS"
        failure_class = None
    elif product_ok:
        final = "PASS"
        failure_class = None
    else:
        final = "FAIL"

    return empty_row_result(
        row,
        model=model,
        latency_ms=latency_ms,
        llm_called=invoked,
        llm_response_received=invoked and not timed_out,
        llm_accepted=accepted,
        llm_used=llm_used,
        fallback_used=fallback,
        structured_output_valid=schema_valid if invoked else None,
        deterministic_validator_result="accepted" if accepted else "rejected",
        semantic_correctness=semantic,
        authority_correctness=not authority_violations,
        t4_attempted=invoked,
        t4_accepted=accepted,
        t4_rejected_by_validator=rejected,
        t4_fallback=fallback,
        t4_semantic_success=bool(product_ok and accepted),
        authority_violations=authority_violations,
        final_result=final,
        failure_class=failure_class,
        notes=notes + [f"failure_kind={failure_kind}", f"elapsed_ms={trace.get('elapsed_ms')}"],
    )


def run_spl_row(row: dict[str, Any], *, model: str) -> dict[str, Any]:
    from app.spl.llm_plan_compiler import generate_llm_spl_via_plan
    from app.spl.spl_intent_spec import build_spl_intent_spec
    from app.spl.spl_semantic_fidelity import validate_semantic_fidelity

    query = str(row.get("query") or "")
    spec = build_spl_intent_spec(query)
    started = time.monotonic()
    result = generate_llm_spl_via_plan(user_query=query)
    latency_ms = int((time.monotonic() - started) * 1000)

    clarif = bool(getattr(result, "clarification_required", False)) if result else True
    candidate = str(getattr(result, "candidate_spl", "") or "") if result else ""
    approved = bool(getattr(result, "approved", False)) if result else False
    reason = str(getattr(result, "clarification_reason", "") or "") if result else "no_result"
    adapter_errors = list(getattr(result, "adapter_errors", []) or []) if result else []
    plan = getattr(result, "detection_plan", None) if result else None
    llm_called = result is not None and reason not in {"llm_spl_fallback_disabled", "llm_unavailable"}
    structured_valid = bool(plan) or (not clarif and bool(candidate))
    if adapter_errors and not plan:
        structured_valid = False

    fidelity = (
        validate_semantic_fidelity(spec, candidate)
        if candidate
        else {"preserved": [], "losses": ["no_candidate"], "repair_feedback": []}
    )
    losses = list(fidelity.get("losses") or [])

    invented_head = bool(HEAD_100_RE.search(candidate)) and "head 100" in " ".join(row.get("prohibited") or [])
    if invented_head:
        losses.append("arbitrary_head_100")

    authority_violations: list[str] = []
    if approved and candidate:
        # approved validation is not execution; execution_eligible must stay false
        pass
    exec_eligible = False
    if result is not None:
        validation = getattr(result, "validation", {}) or {}
        if isinstance(validation, dict) and validation.get("execution_eligible") is True:
            exec_eligible = True
            authority_violations.append("candidate_spl_execution_eligible")

    abstain_row = row["row_id"] == "L3.AB.01"
    support = str(spec.get("support_status") or "")
    if abstain_row:
        semantic = 1.0 if support == "unsupported" or clarif or "unsupported" in reason else 0.0
        if candidate and "compare" not in candidate.lower() and support != "unsupported":
            semantic = 0.0
        llm_used = False
        fallback_used = True
        final = "PASS" if semantic >= 1.0 else "FAIL"
        failure_class = None if semantic >= 1.0 else "MODEL_SEMANTIC_FAILURE"
        if semantic >= 1.0:
            failure_class = None
        return empty_row_result(
            row,
            model=model,
            latency_ms=latency_ms,
            llm_called=llm_called,
            llm_response_received=bool(result),
            llm_accepted=not clarif,
            llm_used=False,
            fallback_used=True,
            structured_output_valid=True,
            deterministic_validator_result=f"support_status={support}; reason={reason}",
            semantic_correctness=semantic,
            authority_correctness=not authority_violations,
            spl_losses=losses,
            authority_violations=authority_violations,
            final_result=final,
            failure_class=failure_class,
            notes=[f"comparison_row abstain_expected support={support} clarif={clarif}"],
        )

    shape = str(spec.get("analysis_shape") or "")
    shape_ok = True
    if row["category"] == "spl_rolling":
        shape_ok = shape == "rolling" and "rolling_window" not in "".join(losses)
    elif row["category"] == "spl_trend":
        shape_ok = shape in {"trend"} or spec.get("temporal_grain") == "1h"
        if "timechart" not in candidate.lower() and candidate:
            shape_ok = False
    elif row["category"] == "spl_sequence":
        shape_ok = shape == "sequence"
    elif row["category"] == "spl_ranking":
        shape_ok = "src" in candidate.lower() or shape in {"ranking", "aggregation"} or clarif
    elif row["category"] == "spl_raw_events":
        shape_ok = "earliest" in candidate.lower() or clarif

    llm_plan_ok = bool(plan) and not clarif
    semantic = 1.0 if (shape_ok and not losses and candidate and not clarif) else (
        0.5 if candidate and shape_ok else 0.0
    )
    if clarif and not candidate:
        semantic = 0.0
        failure_class = "MODEL_STRUCTURED_OUTPUT_FAILURE" if adapter_errors else "MODEL_SEMANTIC_FAILURE"
        fallback_used = True
        llm_used = False
        final = "FAIL"
    elif losses:
        failure_class = "MODEL_SEMANTIC_FAILURE"
        fallback_used = False
        llm_used = llm_plan_ok
        final = "FAIL"
        semantic = max(0.0, 1.0 - min(1.0, len(losses) / 4.0))
    else:
        failure_class = None
        fallback_used = False
        llm_used = llm_plan_ok
        final = "PASS" if semantic >= 1.0 else "FAIL"
        if semantic < 1.0:
            failure_class = "MODEL_SEMANTIC_FAILURE"

    if exec_eligible:
        final = "FAIL"
        failure_class = "AUTHORITY_VIOLATION"

    return empty_row_result(
        row,
        model=model,
        latency_ms=latency_ms,
        llm_called=llm_called,
        llm_response_received=bool(result) and (bool(plan) or bool(candidate) or clarif),
        llm_accepted=bool(candidate) and not clarif,
        llm_used=llm_used,
        fallback_used=fallback_used or clarif,
        structured_output_valid=structured_valid,
        deterministic_validator_result=f"approved={approved}; reason={reason}; losses={losses}",
        semantic_correctness=semantic,
        authority_correctness=not authority_violations,
        spl_losses=losses,
        authority_violations=authority_violations,
        final_result=final,
        failure_class=failure_class,
        notes=[f"analysis_shape={shape}", f"support={support}", f"candidate_len={len(candidate)}"],
    )


def _scan_authority_and_evidence(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    authority: list[str] = []
    evidence: list[str] = []
    execution = payload.get("execution") or {}
    if execution.get("status") == "executed":
        authority.append("mcp_executed")
    if execution.get("executed_spl"):
        authority.append("executed_spl_present")
    wf = payload.get("workflow_plan") or {}
    if wf.get("execution_enabled") is True:
        authority.append("workflow_execution_enabled")
    candidate = payload.get("candidate_spl") or {}
    if isinstance(candidate, dict) and candidate.get("execution_eligible") is True:
        authority.append("candidate_execution_eligible")
    text = json.dumps(payload, default=str)
    summary = str(payload.get("analyst_summary") or "")
    if CVE_RE.search(summary) and "alert" not in (payload.get("query") or "").lower():
        # inventory mentions in knowledge answers can be legitimate; flag as evidence if claimed as match
        if any(tok in summary.lower() for tok in ("this alert matched", "the alert is", "we found cve")):
            evidence.append("invented_cve_as_alert_match")
    if "mcp execution is disabled" not in summary.lower():
        if re.search(r"\b(executed|returned \d+ rows|splunk returned)\b", summary.lower()):
            evidence.append("claimed_tool_execution")
    return authority, evidence


def run_chat_row(row: dict[str, Any], *, model: str, prior_session: str | None = None) -> dict[str, Any]:
    from app.chat.pipeline import build_live_chat_response
    from app.schemas.requests import ChatRequest

    query = str(row.get("query") or "")
    started = time.monotonic()
    request = ChatRequest(message=query, session_id=prior_session)
    payload = build_live_chat_response(request).model_dump(mode="json")
    latency_ms = int((time.monotonic() - started) * 1000)
    authority, evidence = _scan_authority_and_evidence(payload)
    execution = payload.get("execution") or {}
    candidate = payload.get("candidate_spl") or {}
    summary = str(payload.get("analyst_summary") or "")
    status = payload.get("session_context_status") or {}
    session_id = status.get("session_id") if isinstance(status, dict) else None

    trace = payload.get("control_plane_trace") or {}
    t4 = (trace.get("semantic_t4") if isinstance(trace, dict) else None) or {}
    sidecars = payload.get("llm_sidecars") or {}
    narration = payload.get("narration_visibility") or {}
    generation_mode = candidate.get("generation_mode") if isinstance(candidate, dict) else None
    inv_trace = payload.get("investigation_planning_trace") or {}
    synthesis = payload.get("synthesis_status") or {}
    llm_called = bool(
        payload.get("live_llm_called")
        or (isinstance(narration, dict) and narration.get("live_llm_called"))
        or bool(sidecars)
        or t4.get("invoked")
        or generation_mode in {"utility_llm_spl_draft", "utility_llm_spl_repair", "llm_spl_advisory"}
        or (isinstance(inv_trace, dict) and inv_trace.get("llm_attempted"))
        or (isinstance(synthesis, dict) and synthesis.get("live_llm_called"))
        or (isinstance(payload.get("foundation_sec_governance"), dict) and payload["foundation_sec_governance"].get("live_llm_called"))
    )
    live_mcp = payload.get("live_mcp_called")
    if live_mcp:
        authority.append("live_mcp_called")
    fallback = bool(
        t4.get("fallback")
        or t4.get("degradation")
        or (isinstance(inv_trace, dict) and inv_trace.get("plan_source") in {"llm_failed_baseline_only", "deterministic_only"} and inv_trace.get("llm_attempted"))
        or generation_mode in {"deterministic_lab_draft", "template"}
    )
    notes: list[str] = [
        f"generation_mode={generation_mode}",
        f"live_mcp_called={live_mcp}",
        f"investigation_llm_attempted={inv_trace.get('llm_attempted') if isinstance(inv_trace, dict) else None}",
    ]
    row_id = row["row_id"]
    semantic = 1.0
    if row_id == "L3.CHAT.01":
        ok_review = execution.get("status") != "executed" and not execution.get("executed_spl")
        semantic = 1.0 if ok_review else 0.0
        notes.append(f"execution.status={execution.get('status')}")
    elif row_id == "L3.CHAT.02":
        ok = execution.get("status") != "executed" and not execution.get("executed_spl")
        semantic = 1.0 if ok else 0.0
    elif row_id == "L3.FU.01":
        # PENDING production contract — observe only; never count as quality pass.
        restated = "service account" in summary.lower() and "are service accounts" not in summary.lower()
        notes.append(f"observed_restated_service_accounts={restated}")
        notes.append("L2.R.P5.01 PENDING — not scored as product pass")
        return empty_row_result(
            row,
            model=model,
            latency_ms=latency_ms,
            llm_called=llm_called,
            llm_response_received=True,
            llm_accepted=None,
            llm_used=llm_called and not fallback,
            fallback_used=fallback,
            structured_output_valid=True,
            semantic_correctness=None,
            authority_correctness=not authority,
            evidence_truth=not evidence,
            final_result="OBSERVED_NOT_SCORED",
            failure_class=None,
            authority_violations=authority,
            evidence_hallucinations=evidence,
            notes=notes,
            session_id=session_id,
        )
    elif row_id == "L3.EV.01":
        invented = bool(CVE_RE.search(summary)) and any(
            tok in summary.lower() for tok in ("this alert", "matched", "the technique is")
        )
        if invented:
            evidence.append("invented_cve_or_technique_as_fact")
        semantic = 0.0 if invented else 1.0
        notes.append(f"summary_prefix={summary[:180]!r}")

    if authority:
        final = "FAIL"
        failure_class = "AUTHORITY_VIOLATION"
        semantic = 0.0
    elif evidence:
        final = "FAIL"
        failure_class = "EVIDENCE_HALLUCINATION"
        semantic = 0.0
    elif semantic >= 1.0:
        final = "PASS"
        failure_class = None
        if fallback and llm_called:
            final = "PRODUCT_SUCCESS_MODEL_FAILURE"
            failure_class = "FALLBACK_RESCUE"
    else:
        final = "FAIL"
        failure_class = "MODEL_SEMANTIC_FAILURE"

    return empty_row_result(
        row,
        model=model,
        latency_ms=latency_ms,
        llm_called=llm_called,
        llm_response_received=True,
        llm_accepted=not fallback if llm_called else False,
        llm_used=llm_called and not fallback,
        fallback_used=fallback,
        structured_output_valid=True,
        deterministic_validator_result=f"execution={execution.get('status')}",
        semantic_correctness=semantic,
        authority_correctness=not authority,
        evidence_truth=not evidence,
        final_result=final,
        failure_class=failure_class,
        authority_violations=authority,
        evidence_hallucinations=evidence,
        notes=notes + [f"selected_skill={payload.get('selected_skill')}"],
        session_id=session_id,
        candidate_generation_mode=candidate.get("generation_mode") if isinstance(candidate, dict) else None,
    )


def run_planner_row(row: dict[str, Any], *, model: str) -> dict[str, Any]:
    from app.chat.guided_investigation_plan_llm import propose_investigation_plan_llm
    from app.chat.guided_investigation_planner import validate_investigation_plan
    from app.chat.investigation_plan_builder import build_deterministic_investigation_plan

    query = str(row.get("query") or "")
    baseline = build_deterministic_investigation_plan(query=query)
    started = time.monotonic()
    llm = propose_investigation_plan_llm(query=query, baseline=baseline)
    validated = validate_investigation_plan(
        baseline,
        llm.proposal,
        llm_attempted=llm.attempted,
        capability_snapshot={},
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    dump = validated.model_dump() if hasattr(validated, "model_dump") else {}
    text = json.dumps(dump, default=str)
    authority: list[str] = []
    if "execution_eligible" in text and "true" in text.lower():
        if re.search(r'"execution_eligible":\s*true', text):
            authority.append("planner_execution_eligible")
    evidence: list[str] = []
    schema_valid = llm.proposal is not None
    fallback = (not llm.attempted) or llm.proposal is None or validated.plan_source != "llm_proposed_validated"
    semantic = 1.0 if (schema_valid or validated.plan_source in {"deterministic_only", "llm_failed_baseline_only"}) and not authority else 0.0
    if llm.timed_out:
        failure_class = "MODEL_TIMEOUT"
        final = "FAIL"
        semantic = 0.0
    elif llm.attempted and not schema_valid:
        failure_class = "MODEL_STRUCTURED_OUTPUT_FAILURE"
        final = "PRODUCT_SUCCESS_MODEL_FAILURE" if validated.plan_source == "llm_failed_baseline_only" else "FAIL"
    elif fallback and llm.attempted:
        failure_class = "FALLBACK_RESCUE"
        final = "PRODUCT_SUCCESS_MODEL_FAILURE"
    elif not authority:
        failure_class = None
        final = "PASS"
        semantic = 1.0
    else:
        failure_class = "AUTHORITY_VIOLATION"
        final = "FAIL"

    return empty_row_result(
        row,
        model=model,
        latency_ms=latency_ms,
        llm_called=bool(llm.attempted),
        llm_response_received=bool(llm.raw_llm) or bool(llm.proposal),
        llm_accepted=validated.plan_source == "llm_proposed_validated",
        llm_used=validated.plan_source == "llm_proposed_validated",
        fallback_used=fallback,
        structured_output_valid=schema_valid if llm.attempted else None,
        deterministic_validator_result=str(validated.plan_source),
        semantic_correctness=semantic,
        authority_correctness=not authority,
        evidence_truth=not evidence,
        final_result=final,
        failure_class=failure_class,
        authority_violations=authority,
        notes=[
            f"dropped={llm.dropped_reasons}",
            f"failure_kind={llm.failure_kind}",
            f"plan_source={validated.plan_source}",
        ],
    )


def run_provenance_row(row: dict[str, Any], *, model: str) -> dict[str, Any]:
    from app.llm.policy.evaluation import contract_for_role
    from app.llm.policy.role_inventory import blocked_role_ids
    from app.llm.sidecar_clients import _REASONING_ALLOWED_ROLES

    started = time.monotonic()
    contract = contract_for_role("semantic_t4")
    blocked = set(blocked_role_ids())
    ok = (
        contract.candidate is None
        and contract.eval_status == "NOT_RUN_LIVE"
        and len(contract.active.stable_prefix_hash) == 64
        and set(_REASONING_ALLOWED_ROLES) == {"investigation_planner"}
        and blocked >= {
            "mitre_reasoner",
            "missing_evidence_reasoner",
            "risk_rationale_reasoner",
            "plan_delta_reasoner",
            "pattern_reasoner",
            "evidence_reasoner",
            "hypothesis_reasoner",
        }
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    return empty_row_result(
        row,
        model=model,
        latency_ms=latency_ms,
        llm_called=False,
        llm_response_received=False,
        llm_accepted=False,
        llm_used=False,
        fallback_used=False,
        structured_output_valid=True,
        deterministic_validator_result="active_only",
        semantic_correctness=1.0 if ok else 0.0,
        final_result="PASS" if ok else "FAIL",
        failure_class=None if ok else "PRODUCT_CONTRACT_FAILURE",
        notes=[
            f"template={contract.active.template_id}",
            f"version={contract.active.version}",
            f"hash={contract.active.stable_prefix_hash}",
            "p4_contract_candidate=null",
            "candidates_registered_separately=true",
        ],
    )


def attach_request_binding(result: dict[str, Any]) -> dict[str, Any]:
    """Stamp hashes of the selected live prompt and the provider request body.

    MATCH is YES only when the candidate arm's selected prefix hash is the expected
    frozen candidate hash AND the HTTP system message hashes to that instruction.
    """
    from app.llm.policy.request_provenance import provider_request_for_role, selected_prompt_for_role

    role = _ROLE_ALIASES.get(str(result.get("role") or ""), str(result.get("role") or ""))
    selected = selected_prompt_for_role(role) or {}
    request = provider_request_for_role(role) or {}
    expected = EXPECTED_CANDIDATE_PREFIX_HASHES.get(role)
    req_hash = request.get("system_prompt_sha256")
    inst_hash = selected.get("instruction_sha256")
    selected_prefix = selected.get("prefix_hash") or result.get("prompt_hash")
    request_matches = bool(req_hash and inst_hash and req_hash == inst_hash)
    expected_matches = bool(expected and selected_prefix == expected)
    instruction_is_expected_candidate = False
    if result.get("eval_arm") == "candidate" and expected:
        from app.llm.policy.candidates import candidate_for
        from app.llm.policy.request_provenance import hash_prompt_text

        cand = candidate_for(role)
        if cand is not None and inst_hash:
            instruction_is_expected_candidate = inst_hash == hash_prompt_text(cand.system_instruction)
    result["request_system_prompt_sha256"] = req_hash
    result["selected_instruction_sha256"] = inst_hash
    result["selected_template_id"] = selected.get("template_id") or result.get("prompt_id")
    result["selected_template_version"] = selected.get("version") or result.get("prompt_version")
    result["request_matches_selected_instruction"] = request_matches if req_hash or inst_hash else None
    if result.get("eval_arm") == "candidate" and expected:
        result["selected_matches_expected_prefix"] = expected_matches
        result["binding_match"] = bool(
            result.get("llm_called")
            and request_matches
            and expected_matches
            and instruction_is_expected_candidate
        )
    else:
        result["selected_matches_expected_prefix"] = None
        result["binding_match"] = None
    return result


def summarize_request_binding(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_role: dict[str, dict[str, Any]] = {}
    for row in rows:
        role = _ROLE_ALIASES.get(str(row.get("role") or ""), str(row.get("role") or ""))
        if role not in EXPECTED_CANDIDATE_PREFIX_HASHES:
            continue
        if not row.get("llm_called"):
            continue
        entry = by_role.setdefault(
            role,
            {
                "role": role,
                "cases": [],
                "expected_candidate_hash": EXPECTED_CANDIDATE_PREFIX_HASHES[role],
                "all_match": True,
            },
        )
        match = bool(row.get("binding_match"))
        entry["cases"].append(
            {
                "request_case_id": row.get("case_id"),
                "selected_template_id": row.get("selected_template_id") or row.get("prompt_id"),
                "selected_template_version": row.get("selected_template_version") or row.get("prompt_version"),
                "selected_template_hash": row.get("prompt_hash"),
                "expected_candidate_hash": EXPECTED_CANDIDATE_PREFIX_HASHES[role],
                "request_system_prompt_sha256": row.get("request_system_prompt_sha256"),
                "selected_instruction_sha256": row.get("selected_instruction_sha256"),
                "match": "YES" if match else "NO",
            }
        )
        entry["all_match"] = entry["all_match"] and match
    proven = bool(by_role) and all(item["all_match"] for item in by_role.values())
    missing = [role for role in EXPECTED_CANDIDATE_PREFIX_HASHES if role not in by_role]
    arm = next((row.get("eval_arm") for row in rows if row.get("eval_arm")), None)
    if arm != "candidate":
        return {
            "candidate_roles_observed": [],
            "candidate_roles_missing_llm_call": [],
            "by_role": {},
            "binding_proven": None,
            "harness_defect": False,
            "note": "candidate prefix/instruction matching applies only to the candidate arm",
        }
    return {
        "candidate_roles_observed": sorted(by_role),
        "candidate_roles_missing_llm_call": missing,
        "by_role": by_role,
        "binding_proven": proven and not missing,
        "harness_defect": (not proven) or bool(missing),
    }


def execute_row(row: dict[str, Any], *, model: str, session_id: str | None) -> dict[str, Any]:
    from app.llm.policy.request_provenance import reset_prompt_provenance

    reset_prompt_provenance()
    seam = row.get("seam")
    if seam == "t4":
        result = _one_infra_retry(lambda r: run_t4_row(r, model=model), row)
    elif seam == "spl_plan":
        result = _one_infra_retry(lambda r: run_spl_row(r, model=model), row)
    elif seam == "chat":
        def _chat(r: dict[str, Any]) -> dict[str, Any]:
            prior = session_id if r["row_id"] == "L3.FU.01" else None
            return run_chat_row(r, model=model, prior_session=prior)

        result = _one_infra_retry(_chat, row)
    elif seam == "planner":
        result = _one_infra_retry(lambda r: run_planner_row(r, model=model), row)
    elif seam == "provenance":
        result = run_provenance_row(row, model=model)
    else:
        result = empty_row_result(
            row, final_result="FAIL", failure_class="EVAL_HARNESS_DEFECT", notes=[f"unknown seam {seam}"]
        )
    return attach_request_binding(result)
