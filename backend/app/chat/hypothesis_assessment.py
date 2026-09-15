"""Bounded hypothesis assessment against admitted SourceEvidence.

This is not a second planner, agent, or hypothesis state machine. InvestigationPlan
hypotheses stay the analytical objects; this module reassesses them after
SourceEvidence admission using the existing governed evidence projection.

Public InvestigationOutcome still exposes only supported_hypotheses and
unconfirmed_hypotheses. ``weakened`` is internal metadata used to lower priority,
explain the next evidence gap, and narrate evolution.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.evidence.governed_reasoning_context import (
    ADMITTED_STATUSES,
    ENVIRONMENT_SOURCE_TYPES,
    FAILED_STATUSES,
    RAG_SOURCE_TYPES,
    USER_CLAIM_SOURCE_TYPES,
    project_source_evidence_for_reasoning,
)
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.sidecar_clients import invoke_sidecar_role_with_metadata

HYPOTHESIS_ASSESSMENT_SCHEMA = "hypothesis_assessment_v1"
HYPOTHESIS_ASSESSMENT_ROLE = "evidence_reasoner"
ASSESSMENT_VALUES = frozenset({"supported", "unconfirmed", "weakened"})
PUBLIC_STATES = frozenset({"supported", "unconfirmed"})
_ASSESSMENT_TIMEOUT_SECONDS = 30.0
_PRIORITY = {"supported": 1, "unconfirmed": 2, "weakened": 3}


def evidence_fingerprint(source_evidence: list[dict[str, Any]] | None) -> str:
    ids = sorted(admitted_environment_ids(source_evidence))
    encoded = json.dumps(ids, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def admitted_environment_ids(source_evidence: list[dict[str, Any]] | None) -> set[str]:
    ids: set[str] = set()
    for item in source_evidence or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("source_type") or "") not in ENVIRONMENT_SOURCE_TYPES:
            continue
        if str(item.get("collection_status") or "") not in ADMITTED_STATUSES:
            continue
        evidence_id = str(item.get("evidence_id") or "").strip()
        if evidence_id:
            ids.add(evidence_id)
    return ids


def disallowed_support_ids(source_evidence: list[dict[str, Any]] | None) -> set[str]:
    """IDs that must never corroborate a hypothesis (RAG, user claims, failed tools)."""
    ids: set[str] = set()
    for item in source_evidence or []:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidence_id") or "").strip()
        if not evidence_id:
            continue
        source_type = str(item.get("source_type") or "")
        status = str(item.get("collection_status") or "")
        if source_type in USER_CLAIM_SOURCE_TYPES or source_type in RAG_SOURCE_TYPES:
            ids.add(evidence_id)
        if status in FAILED_STATUSES:
            ids.add(evidence_id)
        if str(item.get("plan_step_ref") or "") == "rag":
            ids.add(evidence_id)
    return ids


def hypotheses_from_plan(
    plan: dict[str, Any] | None,
    resolved_query: dict[str, Any] | None = None,
) -> list[str]:
    hypotheses: list[str] = []
    for source in (
        (plan or {}).get("hypotheses"),
        (resolved_query or {}).get("competing_hypotheses"),
    ):
        for item in source or []:
            text = str(item or "").strip()
            if text and text not in hypotheses:
                hypotheses.append(text)
    return hypotheses


def hypotheses_from_state(state: dict[str, Any]) -> list[str]:
    plan = state.get("validated_investigation_plan")
    if not isinstance(plan, dict):
        approval = state.get("investigation_approval")
        plan = approval.get("validated_plan") if isinstance(approval, dict) else None
    rqc = state.get("resolved_query_contract")
    return hypotheses_from_plan(
        plan if isinstance(plan, dict) else {},
        rqc if isinstance(rqc, dict) else {},
    )


def stable_hypothesis_items(
    hypotheses: list[str],
    prior: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Assign stable hN ids by first-seen exact text. No fuzzy matching."""
    prior_by_text: dict[str, str] = {}
    used: set[str] = set()
    for item in (prior or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        hid = str(item.get("hypothesis_id") or "").strip()
        if text and hid:
            prior_by_text[text] = hid
            used.add(hid)
    next_n = 1
    items: list[dict[str, Any]] = []
    for text in hypotheses:
        hid = prior_by_text.get(text)
        if not hid:
            while f"h{next_n}" in used:
                next_n += 1
            hid = f"h{next_n}"
            used.add(hid)
            next_n += 1
        items.append({"hypothesis_id": hid, "text": text})
    return items


def ledger_for_prompt(
    hypotheses: list[str],
    prior: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    prior_by_id = {
        str(item.get("hypothesis_id")): item
        for item in (prior or {}).get("items") or []
        if isinstance(item, dict) and item.get("hypothesis_id")
    }
    rows: list[dict[str, Any]] = []
    for item in stable_hypothesis_items(hypotheses, prior):
        previous = prior_by_id.get(item["hypothesis_id"]) or {}
        rows.append(
            {
                "hypothesis_id": item["hypothesis_id"],
                "text": item["text"],
                "assessment": str(previous.get("assessment") or "unconfirmed"),
                "priority": int(previous.get("priority") or _PRIORITY["unconfirmed"]),
            }
        )
    return rows


def _public_state(assessment: str) -> str:
    return "supported" if assessment == "supported" else "unconfirmed"


def _clean_refs(values: Any, allowed: set[str]) -> list[str]:
    refs: list[str] = []
    for item in values or []:
        ref = str(item or "").strip()
        if ref and ref in allowed and ref not in refs:
            refs.append(ref)
    return refs


def validate_advisory_assessments(
    *,
    hypotheses: list[str],
    advisory: list[Any] | None,
    source_evidence: list[dict[str, Any]] | None,
    prior: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """DET-authoritative assessment package. Advisory cannot invent support."""
    env_ids = admitted_environment_ids(source_evidence)
    blocked_ids = disallowed_support_ids(source_evidence)
    fingerprint = evidence_fingerprint(source_evidence)
    identity = stable_hypothesis_items(hypotheses, prior)
    prior_by_id = {
        str(item.get("hypothesis_id")): item
        for item in (prior or {}).get("items") or []
        if isinstance(item, dict)
    }
    advisory_by_id: dict[str, dict[str, Any]] = {}
    advisory_by_text: dict[str, dict[str, Any]] = {}
    for raw in advisory or []:
        if not isinstance(raw, dict):
            continue
        hid = str(raw.get("hypothesis_id") or "").strip()
        text = str(raw.get("text") or "").strip()
        if hid:
            advisory_by_id[hid] = raw
        if text:
            advisory_by_text[text] = raw

    items: list[dict[str, Any]] = []
    for identity_row in identity:
        hid = identity_row["hypothesis_id"]
        text = identity_row["text"]
        previous = prior_by_id.get(hid) or {}
        proposed = advisory_by_id.get(hid) or advisory_by_text.get(text) or {}
        assessment = "unconfirmed"
        rationale = ""
        supporting: list[str] = []
        contradicting: list[str] = []
        material_gap = ""
        confidence: str | None = None
        if env_ids and proposed:
            wanted = str(proposed.get("assessment") or "unconfirmed").strip().lower()
            if wanted not in ASSESSMENT_VALUES:
                wanted = "unconfirmed"
            supporting = _clean_refs(proposed.get("supporting_source_refs"), env_ids - blocked_ids)
            contradicting = _clean_refs(
                proposed.get("contradicting_source_refs"), env_ids - blocked_ids
            )
            rationale = str(proposed.get("rationale") or "").strip()[:500]
            material_gap = str(proposed.get("material_gap") or "").strip()[:240]
            raw_confidence = str(proposed.get("confidence") or "").strip().lower()
            if raw_confidence in {"low", "medium", "high"}:
                confidence = raw_confidence
            if wanted == "supported" and supporting and rationale:
                assessment = "supported"
            elif wanted == "weakened" and contradicting and rationale:
                assessment = "weakened"
            else:
                assessment = "unconfirmed"
                if wanted == "supported":
                    supporting = []
                if wanted == "weakened":
                    contradicting = []
        elif previous.get("assessment") in ASSESSMENT_VALUES and (
            str(previous.get("evidence_fingerprint") or "") == fingerprint
        ):
            assessment = str(previous.get("assessment"))
            rationale = str(previous.get("rationale") or "")
            supporting = list(previous.get("supporting_source_refs") or [])
            contradicting = list(previous.get("contradicting_source_refs") or [])
            material_gap = str(previous.get("material_gap") or "")
            confidence = previous.get("confidence") if previous.get("confidence") in {"low", "medium", "high"} else None
        row = {
            "hypothesis_id": hid,
            "text": text,
            "assessment": assessment,
            "public_state": _public_state(assessment),
            "rationale": rationale,
            "supporting_source_refs": supporting,
            "contradicting_source_refs": contradicting,
            "material_gap": material_gap,
            "priority": _PRIORITY[assessment],
            "evidence_fingerprint": fingerprint,
        }
        if confidence:
            row["confidence"] = confidence
        items.append(row)

    history = [
        dict(entry)
        for entry in (prior or {}).get("history") or []
        if isinstance(entry, dict)
    ]
    if not history:
        history.append(
            {
                "evidence_fingerprint": "initial",
                "items": [
                    {
                        "hypothesis_id": identity_row["hypothesis_id"],
                        "text": identity_row["text"],
                        "assessment": "unconfirmed",
                        "public_state": "unconfirmed",
                        "priority": _PRIORITY["unconfirmed"],
                    }
                    for identity_row in identity
                ],
            }
        )
    snapshot = {
        "evidence_fingerprint": fingerprint,
        "items": [
            {
                "hypothesis_id": item["hypothesis_id"],
                "text": item["text"],
                "assessment": item["assessment"],
                "public_state": item["public_state"],
                "priority": item["priority"],
            }
            for item in items
        ],
    }
    last_fp = str((history[-1] or {}).get("evidence_fingerprint") or "") if history else ""
    if fingerprint != last_fp:
        history.append(snapshot)

    return {
        "schema_version": HYPOTHESIS_ASSESSMENT_SCHEMA,
        "evidence_fingerprint": fingerprint,
        "items": items,
        "history": history[-8:],
        "evolution_summary": evolution_summary_from_package({"items": items, "history": history}),
    }


def public_hypothesis_lists(package: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    supported: list[str] = []
    unconfirmed: list[str] = []
    for item in (package or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if str(item.get("public_state") or "") == "supported":
            supported.append(text)
        else:
            unconfirmed.append(text)
    return supported, unconfirmed


def evolution_summary_from_package(package: dict[str, Any] | None) -> str:
    """Analyst-facing evolution prose. Internal IDs are omitted."""
    items = [item for item in (package or {}).get("items") or [] if isinstance(item, dict)]
    history = [entry for entry in (package or {}).get("history") or [] if isinstance(entry, dict)]
    if not items:
        return ""
    evidence_rounds = [
        entry
        for entry in history
        if str(entry.get("evidence_fingerprint") or "") not in {"", "initial"}
    ]
    if len(evidence_rounds) >= 2:
        baseline_entries = evidence_rounds[-2].get("items") or []
    elif history:
        baseline_entries = history[0].get("items") or []
    else:
        baseline_entries = []
    first_by_id: dict[str, dict[str, Any]] = {}
    for item in baseline_entries:
        if isinstance(item, dict) and item.get("hypothesis_id"):
            first_by_id[str(item["hypothesis_id"])] = item
    if len(evidence_rounds) >= 2:
        previous = {
            str(item.get("hypothesis_id")): str(item.get("assessment") or "unconfirmed")
            for item in baseline_entries
            if isinstance(item, dict)
        }
        current = {
            str(item.get("hypothesis_id")): str(item.get("assessment") or "unconfirmed")
            for item in items
        }
        if previous and previous == current:
            return "Admitted evidence did not materially change the competing hypotheses."
    parts: list[str] = []
    for item in items:
        hid = str(item.get("hypothesis_id") or "")
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        start = str((first_by_id.get(hid) or {}).get("assessment") or "unconfirmed")
        end = str(item.get("assessment") or "unconfirmed")
        if start == end:
            continue
        short = text if len(text) <= 160 else text[:157] + "..."
        reason = str(item.get("rationale") or "").strip()
        refs = [
            str(ref)
            for ref in (
                item.get("supporting_source_refs") or item.get("contradicting_source_refs") or []
            )
            if str(ref).strip()
        ]
        clause = f"The hypothesis that {short} moved from {start} to {end}"
        if reason:
            clause += f" because {reason.rstrip('.')}"
        if refs:
            clause += f", grounded in {', '.join(refs[:4])}"
        parts.append(clause + ".")
    if not parts:
        if len(evidence_rounds) < 2:
            return ""
        return "Admitted evidence did not materially change the competing hypotheses."
    return " ".join(parts)[:1200]


def assessments_from_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("hypothesis_assessments")
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("assessments")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def build_hypothesis_assessment_prompt(
    *,
    hypotheses: list[str],
    source_evidence: list[dict[str, Any]] | None,
    prior: dict[str, Any] | None = None,
) -> str:
    projected = project_source_evidence_for_reasoning(source_evidence)
    return json.dumps(
        {
            "current_hypotheses": ledger_for_prompt(hypotheses, prior),
            "admitted_environment_evidence": projected["admitted_environment_evidence"],
            "rag_guidance": projected["rag_guidance"],
            "failed_tool_observations": projected["failed_tool_observations"],
            "instruction": (
                "Assess each current hypothesis against admitted environment evidence only. "
                "Return JSON {\"hypothesis_assessments\": [{\"hypothesis_id\", \"assessment\", "
                "\"rationale\", \"supporting_source_refs\", \"contradicting_source_refs\", "
                "\"material_gap\"}]}. assessment is supported, unconfirmed, or weakened. "
                "Support only with admitted environment evidence_id values plus a grounded "
                "rationale. RAG, user claims, tool availability, MCP status, SPL drafts, and "
                "failed tools cannot support or weaken. Absence of evidence is not contradiction. "
                "Do not invent hypotheses. No writes or execution authority."
            ),
        },
        sort_keys=True,
    )


def assess_hypotheses(
    *,
    hypotheses: list[str],
    source_evidence: list[dict[str, Any]] | None,
    prior: dict[str, Any] | None = None,
    raw_output_provider: Any | None = None,
    turn_budget: Any | None = None,
) -> dict[str, Any]:
    """Standalone evidence-reasoner hop used when PlanDelta does not run."""
    empty = validate_advisory_assessments(
        hypotheses=hypotheses,
        advisory=None,
        source_evidence=source_evidence,
        prior=prior,
    )
    if not hypotheses:
        return {**empty, "trace": {"role": HYPOTHESIS_ASSESSMENT_ROLE, "attempted": False}}
    if not admitted_environment_ids(source_evidence):
        return {
            **empty,
            "trace": {
                "role": HYPOTHESIS_ASSESSMENT_ROLE,
                "attempted": False,
                "skipped_reason": "no_admitted_environment_evidence",
            },
        }
    prompt = build_hypothesis_assessment_prompt(
        hypotheses=hypotheses,
        source_evidence=source_evidence,
        prior=prior,
    )
    if raw_output_provider is not None:
        raw = str(raw_output_provider() or "")
        trace = {
            "role": HYPOTHESIS_ASSESSMENT_ROLE,
            "provider": "test_provider",
            "authority": "advisory",
            "attempted": True,
        }
    else:
        hop_timeout = _ASSESSMENT_TIMEOUT_SECONDS
        if turn_budget is not None:
            if turn_budget.time_budget_exhausted():
                return {
                    **empty,
                    "trace": {
                        "role": HYPOTHESIS_ASSESSMENT_ROLE,
                        "attempted": False,
                        "skipped_reason": "turn_budget_exhausted",
                    },
                }
            capped = turn_budget.capped_hop_timeout_seconds(
                role=HYPOTHESIS_ASSESSMENT_ROLE, min_seconds=1.0
            )
            if capped is None:
                return {
                    **empty,
                    "trace": {
                        "role": HYPOTHESIS_ASSESSMENT_ROLE,
                        "attempted": False,
                        "skipped_reason": "turn_budget_exhausted",
                    },
                }
            hop_timeout = min(_ASSESSMENT_TIMEOUT_SECONDS, capped)
        invocation = invoke_sidecar_role_with_metadata(
            role=HYPOTHESIS_ASSESSMENT_ROLE,
            user_prompt=prompt,
            max_tokens=700,
            timeout_seconds=hop_timeout,
            temperature=0.0,
            allow_failover=False,
        )
        raw = str(invocation.raw_output or "")
        trace = {
            "role": HYPOTHESIS_ASSESSMENT_ROLE,
            "provider": invocation.answered_label,
            "authority": "advisory",
            "attempted": True,
            "empty_output": not raw,
            "timed_out": invocation.timed_out,
            "failure_kind": invocation.failure_kind,
        }
    extraction = extract_first_json_object(raw)
    package = validate_advisory_assessments(
        hypotheses=hypotheses,
        advisory=assessments_from_payload(extraction.payload),
        source_evidence=source_evidence,
        prior=prior,
    )
    package["trace"] = {**trace, "accepted": True}
    return package


def refresh_hypothesis_assessments(state: dict[str, Any]) -> dict[str, Any]:
    """Re-assess when admitted environment evidence has changed since the last package."""
    hypotheses = hypotheses_from_state(state)
    source_evidence = [
        item for item in (state.get("source_evidence") or []) if isinstance(item, dict)
    ]
    prior = state.get("hypothesis_assessments")
    prior = prior if isinstance(prior, dict) else None
    fingerprint = evidence_fingerprint(source_evidence)
    if prior and str(prior.get("evidence_fingerprint") or "") == fingerprint:
        return state
    if not hypotheses:
        return state
    package = assess_hypotheses(
        hypotheses=hypotheses,
        source_evidence=source_evidence,
        prior=prior,
        turn_budget=state.get("llm_turn_budget"),
    )
    trace = package.pop("trace", None)
    turn_budget = state.get("llm_turn_budget")
    if isinstance(trace, dict) and trace.get("attempted") and turn_budget is not None:
        turn_budget.record_sidecar(
            role=HYPOTHESIS_ASSESSMENT_ROLE,
            provider_label=trace.get("provider"),
            outcome="completed",
            counts_against_quota=False,
        )
    updated = {**state, "hypothesis_assessments": package}
    if isinstance(trace, dict):
        updated["hypothesis_assessment_trace"] = trace
    return updated
