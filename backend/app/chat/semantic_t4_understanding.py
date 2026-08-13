"""Bounded T4 semantic understanding hop (Plan 5 B4).

Default-off. T1–T3 never pay. One hop, no failover chain. Timeout/error keeps the
deterministic ResolvedQueryContract. The model cannot set a skill, reduce required
capabilities, remove prohibitions, or clear clarification/safety constraints.
Proposed extra required capabilities are accepted only when the accepted intent
family already requires them — widening is rejected, not auto-applied.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, get_args

from pydantic import ValidationError

from app.chat.contracts.intent_classification import IntentFamily
from app.chat.contracts.resolved_query import (
    ALLOWED_CAPABILITIES,
    AmbiguityState,
    ResolvedQueryContract,
)
from app.chat.contracts.semantic_t4_proposal import SemanticT4Proposal
from app.chat.resolved_query_builder import capabilities_for_intent_family
from app.config import settings
from app.llm.adapter.output_preprocessor import preprocess_llm_output
from app.llm.clients.endpoint_resolver import resolve_local_primary_endpoint
from app.llm.clients.local_chat_client import LocalChatClient
from app.llm.sidecar_governance import SidecarLlmCallResult, run_sidecar_llm_with_timeout

SEMANTIC_T4_TIMEOUT_SECONDS = 2.0
_KNOWN_FAMILIES = frozenset(get_args(IntentFamily))
_AMBIGUITY_RANK: dict[str, int] = {
    "unambiguous": 0,
    "insufficient_signals": 1,
    "clarification_required": 2,
    "policy_blocked": 3,
}

SemanticRawProvider = Callable[[str, ResolvedQueryContract], str]

_SEMANTIC_T4_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "normalized_goal": {"type": "string"},
        "intent_family": {"type": "string"},
        "answer_goal": {"type": "string"},
        "ambiguity_state": {"type": "string"},
        "clarification_required": {"type": "boolean"},
        "clarification_reason": {"type": "string"},
        "required_capabilities": {"type": "array"},
        "prohibited_capabilities": {"type": "array"},
        "evidence_requirements": {"type": "array"},
        "entities": {"type": "object"},
        "time_scope": {"type": "string"},
        "confidence": {"type": "number"},
    },
}


def maybe_enrich_t4_semantic(
    deterministic: ResolvedQueryContract,
    *,
    query: str,
    raw_output_provider: SemanticRawProvider | None = None,
) -> ResolvedQueryContract:
    """Return deterministic contract unless T4 + flag-on + a valid bounded hop."""
    if not settings.ai_soc_t4_semantic_understanding_enabled:
        return deterministic
    if deterministic.qualification_tier != "T4":
        return deterministic

    timeout = float(
        settings.ai_soc_t4_semantic_understanding_timeout_seconds or SEMANTIC_T4_TIMEOUT_SECONDS
    )
    started = time.monotonic()
    if raw_output_provider is not None:
        call = _bounded_injected_call(lambda: raw_output_provider(query, deterministic), timeout)
    else:
        call = run_sidecar_llm_with_timeout(
            lambda: _live_single_hop_provider(query, deterministic),
            timeout_seconds=timeout,
            call_purpose="t4_semantic_understanding",
            wrapper_kind="t4_semantic",
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    base_trace: dict[str, Any] = {
        "invoked": True,
        "accepted": False,
        "timed_out": bool(call.timed_out),
        "elapsed_ms": elapsed_ms,
        "timeout_seconds": timeout,
        "rejected_reasons": [],
        "notes": list(call.notes or []),
    }
    if call.timed_out or not call.raw_output:
        reason = "timed_out" if call.timed_out else "empty_output"
        return _with_semantic_trace(deterministic, {**base_trace, "rejected_reasons": [reason]})

    proposal, parse_reason = _parse_proposal(call.raw_output)
    if proposal is None:
        return _with_semantic_trace(
            deterministic, {**base_trace, "rejected_reasons": [parse_reason or "schema_invalid"]}
        )
    return _merge_proposal(deterministic, proposal, base_trace)


def _bounded_injected_call(provider: Callable[[], str], timeout_seconds: float) -> SidecarLlmCallResult:
    """Wall-clock bound for injected providers — does not occupy the live model slot."""
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="t4-semantic-test")
    future = executor.submit(provider)
    try:
        raw = future.result(timeout=timeout_seconds)
        return SidecarLlmCallResult(raw_output=raw, timed_out=False, notes=[])
    except (FuturesTimeoutError, TimeoutError):
        future.cancel()
        return SidecarLlmCallResult(raw_output=None, timed_out=True, notes=["llm_assist_timed_out"])
    except Exception:  # noqa: BLE001 — never propagate provider errors
        return SidecarLlmCallResult(raw_output=None, timed_out=True, notes=["llm_assist_timed_out"])
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _parse_proposal(raw_output: str) -> tuple[SemanticT4Proposal | None, str | None]:
    pre = preprocess_llm_output(raw_output, _SEMANTIC_T4_SCHEMA)
    payload = pre.payload
    if not isinstance(payload, dict):
        return None, "schema_invalid"
    try:
        return SemanticT4Proposal.model_validate(payload), None
    except (ValidationError, ValueError):
        return None, "schema_invalid"


def _merge_proposal(
    deterministic: ResolvedQueryContract,
    proposal: SemanticT4Proposal,
    base_trace: dict[str, Any],
) -> ResolvedQueryContract:
    rejected: list[str] = list(base_trace.get("rejected_reasons") or [])
    field_sources = {
        field: "deterministic_qualification"
        for field in (
            "normalized_goal",
            "intent_family",
            "answer_goal",
            "ambiguity_state",
            "clarification_required",
            "required_capabilities",
            "prohibited_capabilities",
            "evidence_requirements",
            "entities",
            "time_scope",
        )
    }
    accepted_any = False

    intent_family = deterministic.intent_family
    if proposal.intent_family and proposal.intent_family != deterministic.intent_family:
        if _family_change_permitted(deterministic, proposal.intent_family):
            intent_family = proposal.intent_family
            field_sources["intent_family"] = "semantic_t4"
            accepted_any = True
        else:
            rejected.append("intent_family_change_rejected")

    try:
        proposed_required, proposed_prohibited = proposal.capability_sets()
    except ValueError:
        return _with_semantic_trace(
            deterministic, {**base_trace, "rejected_reasons": rejected + ["schema_invalid"]}
        )

    family_required, family_prohibited = capabilities_for_intent_family(intent_family)
    required = set(deterministic.required_capabilities)
    extras = proposed_required - deterministic.required_capabilities
    accepted_extras = extras & family_required
    rejected_extras = extras - accepted_extras
    if rejected_extras:
        rejected.append("capability_widening_rejected")
    if accepted_extras:
        required |= accepted_extras
        field_sources["required_capabilities"] = "semantic_t4"
        accepted_any = True
    if family_required:
        required |= set(family_required)

    # Prohibitions may only be added, and never if they would drop a deterministic required cap.
    added_prohibitions = (proposed_prohibited & ALLOWED_CAPABILITIES) - deterministic.prohibited_capabilities
    conflicting = added_prohibitions & deterministic.required_capabilities
    if conflicting:
        rejected.append("prohibition_would_reduce_required")
        added_prohibitions -= conflicting
    prohibited = set(deterministic.prohibited_capabilities) | added_prohibitions
    if family_prohibited:
        prohibited |= set(family_prohibited) - deterministic.required_capabilities
    if prohibited != set(deterministic.prohibited_capabilities):
        field_sources["prohibited_capabilities"] = "semantic_t4"
        accepted_any = True
    required |= set(deterministic.required_capabilities)
    required -= prohibited - set(deterministic.required_capabilities)

    clarification_required = bool(deterministic.clarification_required)
    clarification_reason = deterministic.clarification_reason
    if proposal.clarification_required is True:
        clarification_required = True
        if proposal.clarification_reason:
            clarification_reason = proposal.clarification_reason
        field_sources["clarification_required"] = "semantic_t4"
        accepted_any = True
    if deterministic.clarification_required:
        clarification_required = True
        clarification_reason = deterministic.clarification_reason or clarification_reason

    ambiguity = deterministic.ambiguity_state
    if proposal.ambiguity_state:
        if _AMBIGUITY_RANK.get(proposal.ambiguity_state, 0) >= _AMBIGUITY_RANK.get(ambiguity, 0):
            if proposal.ambiguity_state != ambiguity:
                ambiguity = proposal.ambiguity_state
                field_sources["ambiguity_state"] = "semantic_t4"
                accepted_any = True
        else:
            rejected.append("ambiguity_weakening_rejected")

    normalized_goal = deterministic.normalized_goal
    if proposal.normalized_goal and proposal.normalized_goal.strip():
        normalized_goal = proposal.normalized_goal.strip()
        field_sources["normalized_goal"] = "semantic_t4"
        accepted_any = True

    answer_goal = deterministic.answer_goal
    if proposal.answer_goal and proposal.answer_goal != deterministic.answer_goal:
        if not clarification_required:
            answer_goal = proposal.answer_goal
            field_sources["answer_goal"] = "semantic_t4"
            accepted_any = True

    entities = dict(deterministic.entities)
    for key, value in (proposal.entities or {}).items():
        if key not in entities or entities[key] in (None, "", [], {}):
            entities[key] = value
            field_sources["entities"] = "semantic_t4"
            accepted_any = True

    time_scope = deterministic.time_scope
    if time_scope in (None, "") and proposal.time_scope:
        time_scope = proposal.time_scope
        field_sources["time_scope"] = "semantic_t4"
        accepted_any = True

    evidence = list(deterministic.evidence_requirements)
    for item in proposal.evidence_requirements:
        if item and item not in evidence:
            evidence.append(item)
            field_sources["evidence_requirements"] = "semantic_t4"
            accepted_any = True

    if clarification_required and not clarification_reason:
        clarification_reason = deterministic.clarification_reason or "semantic_t4_clarification"

    merged = deterministic.model_copy(
        update={
            "normalized_goal": normalized_goal,
            "intent_family": intent_family,
            "answer_goal": answer_goal,
            "ambiguity_state": ambiguity,
            "clarification_required": clarification_required,
            "clarification_reason": clarification_reason,
            "required_capabilities": frozenset(required),
            "prohibited_capabilities": frozenset(prohibited),
            "evidence_requirements": evidence,
            "entities": entities,
            "time_scope": time_scope,
            "understanding_source": "semantic_t4" if accepted_any else "deterministic_qualification",
            "provenance": {
                **dict(deterministic.provenance or {}),
                "field_sources": field_sources,
                "semantic_t4": {
                    **base_trace,
                    "accepted": accepted_any,
                    "rejected_reasons": rejected,
                },
            },
        }
    )
    return merged


def _family_change_permitted(deterministic: ResolvedQueryContract, proposed_family: str) -> bool:
    if proposed_family not in _KNOWN_FAMILIES:
        return False
    if deterministic.clarification_required or deterministic.ambiguity_state in {
        "clarification_required",
        "policy_blocked",
    }:
        return False
    old_req, old_proh = capabilities_for_intent_family(deterministic.intent_family)
    new_req, new_proh = capabilities_for_intent_family(proposed_family)
    if not old_req.issubset(new_req):
        return False
    if new_req - old_req:
        # Additional required capabilities are a widening — not auto-accepted.
        return False
    if not old_proh.issubset(new_proh):
        return False
    return True


def _with_semantic_trace(
    deterministic: ResolvedQueryContract, trace: dict[str, Any]
) -> ResolvedQueryContract:
    provenance = dict(deterministic.provenance or {})
    provenance["semantic_t4"] = trace
    provenance.setdefault(
        "field_sources",
        {key: "deterministic_qualification" for key in ("normalized_goal", "intent_family")},
    )
    return deterministic.model_copy(update={"provenance": provenance})


def _live_single_hop_provider(query: str, deterministic: ResolvedQueryContract) -> str:
    """One LocalChatClient hop — no failover chain. Missing config skips the hop."""
    if settings.ai_soc_llm_mode.strip().lower() in {"mock", "disabled", ""}:
        raise RuntimeError("semantic_t4_llm_disabled")
    if not settings.ai_soc_llm_enabled:
        raise RuntimeError("semantic_t4_llm_disabled")
    endpoint = resolve_local_primary_endpoint(sidecar=True)
    if endpoint is None:
        raise RuntimeError("semantic_t4_no_provider_configured")
    timeout = float(
        settings.ai_soc_t4_semantic_understanding_timeout_seconds or SEMANTIC_T4_TIMEOUT_SECONDS
    )
    client = LocalChatClient(
        base_url=endpoint.base_url,
        model=endpoint.model,
        api_key=endpoint.api_key,
        timeout_seconds=max(1, int(timeout + 0.5)),
    )
    result = client.generate(
        system_prompt=(
            "Return JSON only. Do not add markdown. Do not select a skill. "
            "Do not propose SPL or MCP execution. Propose query understanding only."
        ),
        user_prompt=json.dumps(
            {
                "query": query,
                "deterministic_contract": {
                    "intent_family": deterministic.intent_family,
                    "answer_goal": deterministic.answer_goal,
                    "ambiguity_state": deterministic.ambiguity_state,
                    "clarification_required": deterministic.clarification_required,
                    "required_capabilities": sorted(deterministic.required_capabilities),
                    "prohibited_capabilities": sorted(deterministic.prohibited_capabilities),
                },
            }
        ),
        max_tokens=400,
        temperature=0.1,
        timeout_seconds=timeout,
    )
    return result.text
