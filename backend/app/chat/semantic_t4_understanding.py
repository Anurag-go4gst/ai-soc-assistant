"""Bounded T4 semantic understanding hop (Plan 5 B4).

Default-off. T1–T3 never pay. One hop, no failover chain. Timeout/error keeps the
deterministic ResolvedQueryContract. The model cannot set a skill, reduce required
capabilities, remove prohibitions, or clear clarification/safety constraints.
Proposed extra required capabilities are accepted only when the accepted intent
family already requires them — widening is rejected, not auto-applied.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from pydantic import ValidationError

from app.chat.contracts.resolved_query import (
    ALLOWED_CAPABILITIES,
    AmbiguityState,
    ResolvedQueryContract,
)
from app.chat.complete_or_abstain_gate import (
    MatchCandidate,
    UnderstandingAcceptance,
    evaluate_complete_or_abstain,
)
from app.chat.contracts.explicit_user_constraints import (
    ExplicitUserConstraints,
    build_explicit_user_constraints,
)
from app.chat.contracts.semantic_t4_proposal import (
    FROZEN_SEMANTIC_AMBIGUITY_VALUES,
    FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS,
    OPTIONAL_UNRESOLVED_FILLS,
    SemanticT4Proposal,
)
from app.chat.resolved_query_builder import attach_understanding_authority, capabilities_for_intent_family
from app.config import settings
from app.llm.adapter.output_preprocessor import preprocess_llm_output
from app.llm.clients.endpoint_resolver import resolve_local_primary_endpoint
from app.llm.clients.local_chat_client import LocalChatClient
from app.llm.sidecar_governance import (
    FAILURE_CIRCUIT_OPEN,
    FAILURE_PROVIDER_UNAVAILABLE,
    FAILURE_TIMEOUT,
    NOTE_LLM_ASSIST_TIMED_OUT,
    NOTE_LLM_PROVIDER_UNAVAILABLE,
    SidecarLlmCallResult,
    run_sidecar_llm_with_timeout,
)
from app.safeguards.trust_boundary import CONTROL_PREAMBLE, wrap_untrusted_source

SEMANTIC_T4_TIMEOUT_SECONDS = 2.0
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
        "evidence_requirements": {"type": "array"},
        "competing_hypotheses": {"type": "array"},
        "semantic_ambiguity": {
            "type": "string",
            "enum": list(FROZEN_SEMANTIC_AMBIGUITY_VALUES),
        },
        "clarification_required": {"type": "boolean"},
        "clarification_reason": {"type": "string"},
        "semantic_confidence": {"type": "number"},
        "entities": {"type": "object"},
        "time_scope": {"type": "string"},
        # Legacy aliases — preprocess coercion only; not offered in the frozen schema.
        "ambiguity_state": {"type": "string"},
        "confidence": {"type": "number"},
    },
}


_SEMANTIC_T4_SYSTEM_PROMPT = (
    "Propose the meaning of the whole SOC request after T1-T3 abstained. "
    "Check required referents before ordinary semantic completion.\n"
    "Clarify only if a required referent (event, host, alert, identity, prior turn) is "
    "missing from supplied context, or the ask has two materially "
    "different semantic meanings. Naming a missing referent generically does not resolve "
    "it. Do not emit an unresolved referent as a concrete entity.\n"
    "Do not clarify for missing logs, evidence, examples, thresholds, or detection "
    "criteria. A broad hunt is not missing meaning: resolve it and list evidence "
    "categories.\n"
    "semantic_ambiguity is analyst meaning only. "
    "semantic_confidence is understanding of the ask, not that an attack occurred. "
    "Keep semantic strength: new is not newly registered; unusual is not malicious. "
    "evidence_requirements are evidence categories, not findings. "
    "competing_hypotheses are possibilities, not conclusions.\n"
    "Do not grant route, capability, SPL, MCP, RBAC, HIL, or policy/action authority.\n"
    "Never contradict EXPLICIT_USER_LITERAL_CONSTRAINTS; derived hints are "
    "optional and non-authoritative. One JSON object, no markdown, no prose."
)

# One compact contrastive example for the known failure class:
# clear SOC hunt with missing evidence → do not clarify
# versus unresolved semantic meaning → clarify.
# Prompt asset — not retrieval and not an agent. Not an unseen qualification query.
_SEMANTIC_T4_FEW_SHOT: tuple[dict[str, Any], ...] = (
    {
        "hunt_query": "find signs of lateral movement across the estate",
        "hunt_output": {
            "normalized_goal": "identify signs of lateral movement across the estate",
            "semantic_ambiguity": "unambiguous",
            "clarification_required": False,
            "evidence_requirements": ["internal auth and process hops"],
            "competing_hypotheses": ["admin tooling", "unauthorized movement"],
        },
        "meaning_query": (
            "compare this with what happened last week and tell me if it is getting worse"
        ),
        "meaning_output": {
            "semantic_ambiguity": "clarification_required",
            "clarification_required": True,
            "clarification_reason": "which event 'this' refers to",
        },
    },
)


_UNRESOLVED_TO_SCHEMA: dict[str, str] = {
    "semantic_goal": "normalized_goal",
    "investigation_target": "entities",
}


def _job_aware_unresolved_schema_names(deterministic: ResolvedQueryContract) -> list[str]:
    """Offer the frozen proposal fields, minus locked authority, plus optional fills."""
    locked = dict(deterministic.locked_fields or {})
    blocked = {
        "intent_family",
        "answer_goal",
        "required_capabilities",
        "prohibited_capabilities",
        *list(locked),
    }
    names = [name for name in FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS if name not in blocked]
    unresolved_mapped = [
        _UNRESOLVED_TO_SCHEMA.get(field, field)
        for field in (deterministic.unresolved_fields or ["semantic_goal"])
    ]
    for fill in OPTIONAL_UNRESOLVED_FILLS:
        if fill not in blocked and fill in unresolved_mapped and fill not in names:
            names.append(fill)
    return names


def _schema_limited_to_unresolved(deterministic: ResolvedQueryContract) -> dict[str, Any]:
    allowed = set(_job_aware_unresolved_schema_names(deterministic))
    properties = {
        key: value
        for key, value in _SEMANTIC_T4_SCHEMA["properties"].items()
        if key in allowed
    }
    return {"type": "object", "properties": properties}


# Qualification metadata is not a semantic instruction. Locked clarification is
# already excluded from unresolved_fields_to_resolve; do not ask the model to
# re-decide it.
_PROMPT_LOCKED_KEEP = frozenset(
    {
        "intent_family",
        "answer_goal",
        "prohibited_capabilities",
        "normalized_goal",
        "time_scope",
    }
)


def _prompt_locked_fields(deterministic: ResolvedQueryContract) -> dict[str, Any]:
    """Locked context that can affect semantic interpretation of the ask."""
    locked = dict(deterministic.locked_fields or {})
    if not locked:
        locked = {
            "intent_family": deterministic.intent_family,
            "answer_goal": deterministic.answer_goal,
            "prohibited_capabilities": sorted(deterministic.prohibited_capabilities),
        }
    kept: dict[str, Any] = {}
    for key, value in locked.items():
        if value in (None, "", [], {}):
            continue
        if key.startswith("entities.") or key in _PROMPT_LOCKED_KEEP:
            kept[key] = value
    return kept


def _supplied_context_payload(deterministic: ResolvedQueryContract) -> dict[str, Any] | None:
    """Entities/time already supplied. Omit rather than emit empty sentinels."""
    payload: dict[str, Any] = {}
    entities = {
        key: value
        for key, value in (deterministic.entities or {}).items()
        if value not in (None, "", [], {})
    }
    if entities:
        payload["entities"] = entities
    time_scope = deterministic.time_scope
    if isinstance(time_scope, str) and time_scope.strip():
        payload["time_scope"] = time_scope.strip()
    return payload or None


def _build_semantic_t4_user_prompt(query: str, deterministic: ResolvedQueryContract) -> str:
    """T4 input after a complete T1-T3 ABSTAIN.

    T1-T3 committed no semantic contract, so T4 receives the **original query**
    plus the trusted schema, meaning-aid vocabulary, few-shots, the binding
    EXPLICIT_USER_LITERAL_CONSTRAINTS, and optional non-authoritative derived
    hints. It is deliberately NOT given the old
    ``locked_fields`` + ``unresolved_fields_to_resolve`` patch shape: that asked
    T4 to fill gaps in a partially committed contract, which architecture 2.2
    forbids. T4 proposes meaning for the whole request; DET validates it.
    """
    constraints = explicit_constraints_for(deterministic, query=query)
    example_lines: list[str] = []
    for example in _SEMANTIC_T4_FEW_SHOT:
        example_lines.append(
            "HUNT (missing evidence → do not clarify): " + example["hunt_query"]
        )
        example_lines.append(json.dumps(example["hunt_output"], separators=(",", ":")))
        example_lines.append(
            "MEANING (unresolved referent → clarify): " + example["meaning_query"]
        )
        example_lines.append(json.dumps(example["meaning_output"], separators=(",", ":")))
    from app.llm.policy.candidates import extra_few_shots_for_live

    for extra in extra_few_shots_for_live("semantic_t4"):
        label = str(extra.get("label") or "CANDIDATE")
        example_lines.append(f"{label}: " + str(extra.get("query") or ""))
        example_lines.append(json.dumps(extra.get("output") or {}, separators=(",", ":")))
    task: dict[str, Any] = {"query": query}
    grounding = constraints.to_grounding_payload()
    if grounding:
        # Binding: T4 may use these to understand the request; it may not
        # contradict them, and DET rejects a proposal that does.
        task["EXPLICIT_USER_LITERAL_CONSTRAINTS"] = grounding
    supplied = _supplied_context_payload(deterministic)
    if supplied is not None:
        # Derived observations only — non-authoritative hints T4 may use or reject.
        task["derived_hints_non_authoritative"] = supplied
    return "\n".join(
        [
            CONTROL_PREAMBLE,
            wrap_untrusted_source("user_query", query),
            *example_lines,
            f"TASK: {json.dumps(task, separators=(',', ':'))}",
            "Propose the meaning of the whole request. Never contradict "
            "EXPLICIT_USER_LITERAL_CONSTRAINTS; derived hints are optional.",
            "ANSWER:",
        ]
    )


#: Abstain reasons that resolve the turn *without* a semantic hop. The
#: architecture routes these to clarification / policy handling, not to T4.
_ABSTAIN_REASONS_WITHOUT_T4 = frozenset({"clarification_required", "policy_blocked"})


def _deterministic_semantic_complete(deterministic: ResolvedQueryContract) -> bool:
    """True when DET already resolved every material semantic dimension.

    This is the second ACCEPT arm (architecture complete governed happy path):
    intent family + answer goal known, no clarification/policy block, and no
    real unresolved semantic gaps. Catalogue match_path may still be
    out_of_registry.
    """
    if deterministic.clarification_required:
        return False
    if str(deterministic.ambiguity_state or "") in {"clarification_required", "policy_blocked"}:
        return False
    if list(deterministic.unresolved_fields or ()):
        return False
    family = str(deterministic.intent_family or "").strip()
    if not family or family in {"clarification_required", "unknown"}:
        return False
    goal = str(deterministic.answer_goal or "").strip()
    if not goal or goal == "clarification":
        return False
    sufficiency = deterministic.understanding_sufficiency or {}
    if list(sufficiency.get("missing") or ()):
        return False
    return True


def abstain_acceptance(deterministic: ResolvedQueryContract) -> UnderstandingAcceptance:
    """Project the contract onto the P1 complete-or-abstain gate.

    The gate is the single authority for "did T1-T3 accept a complete governed
    match, or abstain entirely". Nothing here re-implements that decision.
    """
    sufficiency = deterministic.understanding_sufficiency or {}
    provenance = deterministic.provenance or {}
    match_path = str(
        provenance.get("deterministic_match_path")
        or provenance.get("observed_match_path")
        or provenance.get("match_path")
        or getattr(deterministic, "deterministic_match_path", "")
        or deterministic.qualification_source
        or ""
    )
    confidence = getattr(deterministic, "confidence", None)
    candidates: tuple[MatchCandidate, ...] = ()
    if match_path and confidence is not None:
        candidates = (
            MatchCandidate(
                candidate_id=str(provenance.get("use_case_id") or match_path),
                match_path=match_path,
                confidence=float(confidence),
            ),
        )
    return evaluate_complete_or_abstain(
        match_path=match_path,
        candidates=candidates,
        clarification_required=bool(deterministic.clarification_required),
        policy_blocked=str(deterministic.ambiguity_state or "") == "policy_blocked",
        unresolved_fields=tuple(deterministic.unresolved_fields or ()),
        missing_required_fields=tuple(sufficiency.get("missing") or ()),
        semantic_contract_complete=_deterministic_semantic_complete(deterministic),
    )


def _permits_t4_call(deterministic: ResolvedQueryContract) -> bool:
    """T4 runs only after a complete T1-T3 ABSTAIN (architecture 2.2 branch B).

    ACCEPT skips T4 outright. An abstain that already resolves to clarification or
    a policy block also skips it: those turns are answered by the governed
    clarification path, not by a semantic hop.

    Authority is the P1 complete-or-abstain result — not
    ``bool(unresolved_fields)`` and not ``understanding_sufficiency.next_action``.
    """
    acceptance = abstain_acceptance(deterministic)
    if not acceptance.t4_permitted:
        return False
    if _ABSTAIN_REASONS_WITHOUT_T4 & set(acceptance.reason_codes):
        return False
    return True


def _owns_unresolved_semantic_referent(contract: ResolvedQueryContract) -> bool:
    if (contract.provenance or {}).get("t4_owns_unresolved_semantic_referent"):
        return True
    return "semantic_referent" in (contract.unresolved_fields or [])


def _fail_closed_semantic_authority(
    deterministic: ResolvedQueryContract,
    trace: dict[str, Any],
    *,
    clarification_reason: str = "t4_unavailable_unresolved_semantic_referent",
) -> ResolvedQueryContract:
    """T1-T3 abstained and T4 could not resolve meaning: fail closed.

    The turn must not proceed on the abstained deterministic contract. That
    contract carries **no** semantic authority (architecture 2.2 branch B), so
    reusing it here would resurrect exactly the partial understanding the
    complete-or-abstain rule removed, and would let a thin deterministic
    classification stand in as semantic authority. Instead the turn degrades
    visibly to the governed clarification path: no invented Final RQC, no guessed
    route, no accidental investigation lifecycle.
    """
    semantic_trace = {
        **trace,
        "accepted": False,
        "fallback": "deterministic_fail_closed",
        "degradation": True,
        "authority": "t4_unavailable_failover",
        "semantic_authority": "none",
    }
    provenance = dict(deterministic.provenance or {})
    provenance["semantic_t4"] = semantic_trace
    return deterministic.model_copy(
        update={
            "clarification_required": True,
            "clarification_reason": clarification_reason,
            "ambiguity_state": "clarification_required",
            "understanding_source": "deterministic_qualification",
            "provenance": provenance,
        }
    )


def _fail_closed_unresolved_semantic_referent(
    deterministic: ResolvedQueryContract,
    trace: dict[str, Any],
) -> ResolvedQueryContract:
    """Back-compat alias for the unresolved-referent case."""
    return _fail_closed_semantic_authority(deterministic, trace)


def maybe_enrich_t4_semantic(
    deterministic: ResolvedQueryContract,
    *,
    query: str,
    raw_output_provider: SemanticRawProvider | None = None,
) -> ResolvedQueryContract:
    """Return deterministic contract unless T4 + flag-on + CALL_T4 + a valid bounded hop."""
    if not settings.ai_soc_t4_semantic_understanding_enabled:
        # T1–T3 deferred an unresolved referent to a hop that will not run this
        # turn. Deferral is a handoff, and a handoff to a disabled consumer drops
        # the signal: without this the suppressed clarification is simply lost and
        # the turn plans against a query nobody resolved. Same visible degradation
        # the timeout/unavailable paths below already take.
        if _owns_unresolved_semantic_referent(deterministic):
            return _fail_closed_unresolved_semantic_referent(
                deterministic,
                {
                    "invoked": False,
                    "accepted": False,
                    "timed_out": False,
                    "failure_kind": None,
                    "rejected_reasons": ["t4_semantic_understanding_disabled"],
                    "notes": [],
                },
            )
        return deterministic
    if deterministic.qualification_tier != "T4":
        return deterministic
    prepared = (
        deterministic
        if deterministic.understanding_sufficiency
        else attach_understanding_authority(deterministic)
    )
    if not _permits_t4_call(prepared):
        return prepared

    timeout = float(
        settings.ai_soc_t4_semantic_understanding_timeout_seconds or SEMANTIC_T4_TIMEOUT_SECONDS
    )
    started = time.monotonic()
    if raw_output_provider is not None:
        call = _bounded_injected_call(lambda: raw_output_provider(query, prepared), timeout)
    else:
        call = run_sidecar_llm_with_timeout(
            lambda: _live_single_hop_provider(query, prepared),
            timeout_seconds=timeout,
            call_purpose="t4_semantic_understanding",
            wrapper_kind="t4_semantic",
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    # Plan 7 D1: report the failure class the sidecar actually observed. A provider
    # that could not be reached did not "time out", and conflating the two makes the
    # LLM-unavailable and LLM-timeout reliability rows indistinguishable.
    failure_kind = getattr(call, "failure_kind", None)
    real_timeout = bool(call.timed_out) and failure_kind != FAILURE_PROVIDER_UNAVAILABLE
    base_trace: dict[str, Any] = {
        "invoked": True,
        "accepted": False,
        "timed_out": real_timeout,
        "failure_kind": failure_kind,
        "elapsed_ms": elapsed_ms,
        "timeout_seconds": timeout,
        "rejected_reasons": [],
        "notes": list(call.notes or []),
        "circuit_state": getattr(call, "circuit_state", None),
        "human_action_required": bool(getattr(call, "human_action_required", False)),
    }
    if failure_kind == FAILURE_CIRCUIT_OPEN:
        base_trace["invoked"] = False
    if call.timed_out or not call.raw_output:
        if failure_kind == FAILURE_PROVIDER_UNAVAILABLE:
            reason = "provider_unavailable"
        elif failure_kind == FAILURE_TIMEOUT or call.timed_out:
            reason = "timed_out"
        elif failure_kind:
            reason = str(failure_kind)
        else:
            reason = "empty_output"
        failed_trace = {**base_trace, "rejected_reasons": [reason]}
        # T1-T3 abstained, so there is no semantic contract to fall back onto.
        # Unavailable / timeout / circuit-open all fail closed alike.
        return _fail_closed_semantic_authority(
            prepared,
            failed_trace,
            clarification_reason=(
                "t4_unavailable_unresolved_semantic_referent"
                if _owns_unresolved_semantic_referent(prepared)
                else f"t4_semantic_unavailable:{reason}"
            ),
        )

    proposal, parse_reason = _parse_proposal(call.raw_output)
    if proposal is None:
        failed_trace = {
            **base_trace,
            "rejected_reasons": [parse_reason or "schema_invalid"],
        }
        # An invalid structured response is a T4 failure, not a licence to guess.
        return _fail_closed_semantic_authority(
            prepared,
            failed_trace,
            clarification_reason=(
                "t4_unavailable_unresolved_semantic_referent"
                if _owns_unresolved_semantic_referent(prepared)
                else "t4_semantic_invalid_response"
            ),
        )
    return _merge_proposal(prepared, proposal, base_trace, query=query)


def _bounded_injected_call(provider: Callable[[], str], timeout_seconds: float) -> SidecarLlmCallResult:
    """Wall-clock bound for injected providers — does not occupy the live model slot."""
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="t4-semantic-test")
    future = executor.submit(provider)
    try:
        raw = future.result(timeout=timeout_seconds)
        return SidecarLlmCallResult(raw_output=raw, timed_out=False, notes=[])
    except (FuturesTimeoutError, TimeoutError):
        future.cancel()
        return SidecarLlmCallResult(raw_output=None, timed_out=True, notes=[NOTE_LLM_ASSIST_TIMED_OUT], failure_kind=FAILURE_TIMEOUT)
    except Exception:  # noqa: BLE001 — never propagate provider errors
        return SidecarLlmCallResult(
            raw_output=None,
            timed_out=True,
            notes=[NOTE_LLM_PROVIDER_UNAVAILABLE],
            failure_kind=FAILURE_PROVIDER_UNAVAILABLE,
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# Wrappers a model plausibly puts the answer under. Measured: Cisco 8B echoed the
# whole input envelope and nested its answer under "output".
_PROPOSAL_WRAPPER_KEYS = ("output", "answer", "result", "proposal", "response")

# Echoed prompt scaffolding. Present because the model repeated its input; dropping
# it is normalization, not permission — it carries no authority.
_ECHOED_PROMPT_KEYS = frozenset(
    {
        "query",
        "locked_fields_do_not_change",
        "unresolved_fields_to_resolve",
        "vocabulary",
        "examples",
        "deterministic_contract",
        "task",
    }
)

# Keys that would assert authority this stage does not have. Their presence is a
# governance signal, not noise: fail closed rather than quietly strip them.
_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "skill",
        "selected_skill",
        "route",
        "routed_skill",
        "spl",
        "candidate_spl",
        "normalized_spl",
        "tool",
        "tools",
        "mcp",
        "mcp_tool",
        "execute",
        "execution",
        "execution_eligible",
        "rbac",
        "hil",
        "human_review",
        "approved",
        "verdict",
    }
)


def _unwrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Follow a single answer wrapper, then drop echoed prompt scaffolding.

    Deliberately shallow: one wrapper hop. A deeper nest is not a shape this stage
    recognises, and guessing would be inventing structure the model did not commit to.
    """
    for key in _PROPOSAL_WRAPPER_KEYS:
        inner = payload.get(key)
        if isinstance(inner, dict):
            payload = inner
            break
    return {key: value for key, value in payload.items() if key not in _ECHOED_PROMPT_KEYS}


def _parse_proposal(raw_output: str) -> tuple[SemanticT4Proposal | None, str | None]:
    """Normalize a tolerated response shape into the closed proposal schema.

    Shape tolerance is an adapter concern, not a governance relaxation: unknown
    *authority* keys still fail closed, and every accepted field still goes through
    `SemanticT4Proposal` and the deterministic merge.
    """
    pre = preprocess_llm_output(raw_output, _SEMANTIC_T4_SCHEMA)
    payload = pre.payload
    if not isinstance(payload, dict):
        return None, "schema_invalid"

    payload = _unwrap_payload(payload)
    forbidden = sorted(_FORBIDDEN_AUTHORITY_KEYS & set(payload))
    if forbidden:
        return None, "authority_key_present"

    # Unknown non-authority keys are dropped rather than failing the whole hop —
    # a chatty model must not cost a valid semantic completion.
    known = set(SemanticT4Proposal.model_fields)
    payload = {key: value for key, value in payload.items() if key in known}
    if not payload:
        return None, "schema_invalid"
    try:
        return SemanticT4Proposal.model_validate(payload), None
    except (ValidationError, ValueError):
        return None, "schema_invalid"


# Deictic references: the query points at something the analyst has not supplied.
# This — and only this — is semantic uncertainty the analyst can resolve.
_REFERENT_PATTERNS = (
    # Bare "that"/"it" are excluded on purpose: "lookups **that** look generated" is a
    # relative pronoun, not a referent, and treating it as one turned a clear hunt
    # into a clarification (measured in C3).
    r"\bthis\b",
    r"\bthese\b",
    r"\bthose\b",
    r"\bthat (host|alert|event|case|user|account|one|incident|domain|ip)\b",
    r"\bsame (host|alert|user|account|case|incident|thing)\b",
    r"\bearlier\b",
    r"\bprevious(ly)?\b",
    r"\blast time\b",
    r"\bthe (alert|host|user|case|incident|event)\b",
    r"\bit (again|too)\b",
)

# A concrete entity carries a value. A category ("suspicious DNS", "DGA domains")
# does not, and must never be recorded as an observed entity.
_CONCRETE_ENTITY_RE = re.compile(
    r"(\d{1,3}(\.\d{1,3}){3})"  # IPv4
    r"|(CVE-\d{4}-\d{4,})"  # CVE
    r"|([A-Za-z0-9_-]+\.[A-Za-z]{2,})"  # domain / FQDN / file
    r"|(\\\\[^\s]+)"  # UNC path
    r"|([A-Za-z0-9_-]+\\[A-Za-z0-9_.-]+)"  # DOMAIN\user
    r"|(\b[A-Za-z0-9-]*\d[A-Za-z0-9-]*\b)",  # host-like token containing a digit
    re.IGNORECASE,
)

# Time expressions the analyst may actually have written.
_TIME_EXPRESSION_RE = re.compile(
    r"\b(today|yesterday|tonight|overnight|this (week|month|morning|afternoon)"
    r"|last (hour|night|week|month|year|\d+\s*(m|min|minute|h|hour|d|day|w|week)s?)"
    r"|past\s+\d+\s*\w+|previous\s+\w+|\d+\s*(m|min|minute|h|hour|d|day|w|week)s?\s+ago"
    r"|since\s+\w+|between\s+\w+\s+and\s+\w+)\b",
    re.IGNORECASE,
)


def _has_unresolved_referent(query: str) -> bool:
    """True when the query points at something the analyst did not supply."""
    lowered = query.lower()
    return any(re.search(pattern, lowered) for pattern in _REFERENT_PATTERNS)


def _frozen_clarification_claim(proposal: SemanticT4Proposal) -> bool:
    """Complete frozen clarification triple. Does not inspect reason text."""
    if proposal.clarification_required is not True:
        return False
    if proposal.semantic_ambiguity != "clarification_required":
        return False
    reason = proposal.clarification_reason
    return isinstance(reason, str) and bool(reason.strip())


def _locked_fact_contradicts_clarification(deterministic: ResolvedQueryContract) -> bool:
    """Locked T1–T3 meaning, explicit do-not-clarify, or policy block."""
    if deterministic.ambiguity_state == "policy_blocked":
        return True
    locked = deterministic.locked_fields or {}
    if locked.get("ambiguity_state") == "policy_blocked":
        return True
    if "clarification_required" in locked and not bool(locked.get("clarification_required")):
        return True
    if "normalized_goal" in locked:
        return True
    return False


def _semantic_ambiguity_eligible_for_t4(deterministic: ResolvedQueryContract) -> bool:
    """T4 may propose semantic_ambiguity on the ABSTAIN path when not locked away.

    Live ABSTAIN uses the full SemanticT4Proposal schema (not an unresolved-field
    subset), so eligibility is lock-based rather than offered-field-list-based.
    """
    if deterministic.qualification_tier != "T4":
        return False
    locked = deterministic.locked_fields or {}
    return "semantic_ambiguity" not in locked and "clarification_required" not in locked


def _may_merge_t4_clarification(
    deterministic: ResolvedQueryContract,
    proposal: SemanticT4Proposal,
    query: str,
) -> bool:
    """Accept T4 clarification only for the two frozen classes, fail-closed otherwise.

    Class A: unresolved required referent.
    Class B: complete frozen clarification claim, semantic ambiguity eligible for T4,
    and no locked deterministic fact contradicts asking.
    """
    if not _frozen_clarification_claim(proposal):
        return False
    if _locked_fact_contradicts_clarification(deterministic):
        return False
    if _has_unresolved_referent(query):
        return True
    return _semantic_ambiguity_eligible_for_t4(deterministic)


def _is_concrete_entity(value: Any) -> bool:
    text = str(value).strip()
    if not text or len(text.split()) > 3:
        return False
    return bool(_CONCRETE_ENTITY_RE.search(text))


def _entity_value_grounded(
    query: str, deterministic: ResolvedQueryContract, value: Any
) -> bool:
    """A new entity must already appear in the query or supplied/locked context."""
    text = str(value).strip().lower()
    if not text:
        return False
    if text in query.lower():
        return True
    candidates: list[Any] = list((deterministic.entities or {}).values())
    for key, locked_value in (deterministic.locked_fields or {}).items():
        if key == "time_scope" or key.startswith("entities."):
            candidates.append(locked_value)
    if deterministic.time_scope:
        candidates.append(deterministic.time_scope)
    for existing in candidates:
        if isinstance(existing, (list, tuple, set)):
            if any(text == str(item).strip().lower() for item in existing):
                return True
        elif text == str(existing).strip().lower():
            return True
    return False


def _time_scope_grounded(query: str, time_scope: str | None) -> bool:
    """A time scope must come from the analyst, not from the model's habits."""
    if not time_scope:
        return False
    lowered = query.lower()
    if time_scope.strip().lower() in lowered:
        return True
    return bool(_TIME_EXPRESSION_RE.search(lowered))


def _proposed_field_names(proposal: SemanticT4Proposal) -> list[str]:
    """Field names the model actually supplied — names only, never values."""
    dumped = proposal.model_dump(exclude_none=True)
    return sorted(name for name, value in dumped.items() if value not in (None, "", [], {}))


def explicit_constraints_for(
    deterministic: ResolvedQueryContract, *, query: str | None = None
) -> ExplicitUserConstraints:
    """Explicit user literals carried alongside an abstained contract.

    These are USER_INTENT facts, not a T1-T3 semantic commit, so they survive
    abstain and stay binding for DET validation (architecture "Explicit user
    literals vs derived observations").

    Production authority path: ``build_resolved_query_contract`` extracts once
    into ``provenance.explicit_user_constraints``. T4 grounding and DET
    validation read that same object. Re-derivation from ``query`` is a
    test/fallback only when provenance was not populated.
    """
    provenance = deterministic.provenance or {}
    carried = provenance.get("explicit_user_constraints")
    if isinstance(carried, dict):
        return ExplicitUserConstraints(
            entities={k: tuple(v) for k, v in (carried.get("entities") or {}).items()},
            predicates={k: tuple(v) for k, v in (carried.get("predicates") or {}).items()},
            data_scope={k: tuple(v) for k, v in (carried.get("data_scope") or {}).items()},
            time_window=carried.get("time_window"),
            requested_output_type=carried.get("requested_output_type"),
            execution_prohibited=bool(carried.get("execution_prohibited")),
            prohibitions=tuple(carried.get("prohibitions") or ()),
        )
    if not query:
        return ExplicitUserConstraints()
    # Fallback only — production must carry provenance from the DET seam.
    from app.chat.query_signals import extract_query_signals
    from app.spl.user_constraint_bindings import build_user_constraint_bindings

    signals = extract_query_signals(query, None)
    return build_explicit_user_constraints(
        query_understanding=None,
        query_signals=signals,
        bindings=build_user_constraint_bindings(query, query_understanding=None),
    )


def _proposal_literal_view(proposal: SemanticT4Proposal) -> dict[str, Any]:
    """Project the proposal onto the dimensions explicit literals constrain."""
    return {
        "entities": proposal.entities or {},
        "time_scope": proposal.time_scope,
        "requested_output_type": getattr(proposal, "requested_output_type", None),
        "execution_intent": getattr(proposal, "execution_intent", None),
        "execute": getattr(proposal, "execute", None),
    }


def _merge_proposal(
    deterministic: ResolvedQueryContract,
    proposal: SemanticT4Proposal,
    base_trace: dict[str, Any],
    *,
    query: str,
) -> ResolvedQueryContract:
    rejected: list[str] = list(base_trace.get("rejected_reasons") or [])
    # P2-C: DET MUST reject a proposal that materially contradicts an unambiguous
    # explicit user literal (10.0.0.8 must not become 10.0.0.5, "2h" must not become
    # "24h", do_not_execute must not become execute=true). Derived observations are
    # non-authoritative and never trigger this. Checked before any field is adopted.
    contradictions = explicit_constraints_for(deterministic, query=query).material_contradictions(
        _proposal_literal_view(proposal)
    )
    if contradictions:
        return _fail_closed_semantic_authority(
            deterministic,
            {
                **base_trace,
                "rejected_reasons": rejected + ["explicit_literal_contradiction", *contradictions],
            },
            clarification_reason="t4_contradicts_explicit_user_constraints",
        )
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
            "competing_hypotheses",
            "entities",
            "time_scope",
        )
    }
    accepted_any = False

    # `intent_family` and `answer_goal` are LOCKED upstream facts. This stage
    # completes meaning; it does not repair an upstream classification error, and a
    # contract that disagrees with the query is an upstream defect to fix there.
    # (architecture.md §9: T4 may not override locked T1-T3 facts.)
    intent_family = deterministic.intent_family
    if proposal.intent_family and proposal.intent_family != deterministic.intent_family:
        rejected.append("locked_field_change_rejected:intent_family")

    try:
        proposed_required, proposed_prohibited = proposal.capability_sets()
    except ValueError:
        return _with_semantic_trace(
            deterministic, {**base_trace, "rejected_reasons": rejected + ["schema_invalid"]}
        )

    # P2-D: derived fields — required capabilities, evidence requirements, route
    # hints — are recomputed deterministically from the *validated* understanding
    # (architecture 11). A proposal may carry required_capabilities/
    # prohibited_capabilities as schema data, but they never become authority, so
    # nothing below reads `proposed_required` as a source. Any capability the
    # proposal asked for beyond the family-derived set is recorded as rejected.
    family_required, family_prohibited = capabilities_for_intent_family(intent_family)
    required = set(deterministic.required_capabilities)
    rejected_extras = (proposed_required - deterministic.required_capabilities) - set(family_required)
    if rejected_extras:
        rejected.append("capability_widening_rejected")
    if family_required:
        required |= set(family_required)
    field_sources["required_capabilities"] = "deterministic_qualification"

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
        # Value is family-derived, so provenance must not claim semantic_t4 authority.
        field_sources["prohibited_capabilities"] = "deterministic_qualification"
    required |= set(deterministic.required_capabilities)
    required -= prohibited - set(deterministic.required_capabilities)

    clarification_required = bool(deterministic.clarification_required)
    clarification_reason = deterministic.clarification_reason
    may_clarify = _may_merge_t4_clarification(deterministic, proposal, query)
    if proposal.clarification_required is True:
        # Semantic uncertainty only. Evidence/investigation uncertainty must not
        # become an analyst question. Class A = unresolved referent. Class B =
        # complete frozen clarification claim while semantic ambiguity is still
        # eligible for T4 and no locked fact contradicts asking.
        if may_clarify:
            clarification_required = True
            if proposal.clarification_reason:
                clarification_reason = proposal.clarification_reason
            field_sources["clarification_required"] = "semantic_t4"
            accepted_any = True
        else:
            rejected.append("clarification_without_unresolved_referent")
    if deterministic.clarification_required:
        clarification_required = True
        clarification_reason = deterministic.clarification_reason or clarification_reason

    ambiguity = deterministic.ambiguity_state
    if proposal.ambiguity_state:
        if _AMBIGUITY_RANK.get(proposal.ambiguity_state, 0) >= _AMBIGUITY_RANK.get(ambiguity, 0):
            if proposal.ambiguity_state == "clarification_required":
                if not may_clarify:
                    if "clarification_without_unresolved_referent" not in rejected:
                        rejected.append("clarification_without_unresolved_referent")
                elif proposal.ambiguity_state != ambiguity:
                    ambiguity = proposal.ambiguity_state
                    field_sources["ambiguity_state"] = "semantic_t4"
                    accepted_any = True
            elif proposal.ambiguity_state != ambiguity:
                ambiguity = proposal.ambiguity_state
                field_sources["ambiguity_state"] = "semantic_t4"
                accepted_any = True
        else:
            rejected.append("ambiguity_weakening_rejected")

    normalized_goal = deterministic.normalized_goal
    if "normalized_goal" in (deterministic.locked_fields or {}) and proposal.normalized_goal:
        if proposal.normalized_goal.strip() != deterministic.normalized_goal:
            rejected.append("locked_field_change_rejected:normalized_goal")
    elif proposal.normalized_goal and proposal.normalized_goal.strip():
        normalized_goal = proposal.normalized_goal.strip()
        field_sources["normalized_goal"] = "semantic_t4"
        accepted_any = True

    # Locked with `intent_family`, for the same reason. The one exception is a
    # clarification the merge itself accepted: a run that must ask the analyst
    # answers with a clarification, whoever raised it.
    answer_goal = deterministic.answer_goal
    if clarification_required and answer_goal != "clarification":
        answer_goal = "clarification"
    elif proposal.answer_goal and proposal.answer_goal != deterministic.answer_goal:
        rejected.append("locked_field_change_rejected:answer_goal")

    entities = dict(deterministic.entities)
    locked_entity_keys = {
        key.split(".", 1)[1]
        for key in (deterministic.locked_fields or {})
        if key.startswith("entities.") and "." in key
    }
    for key, value in (proposal.entities or {}).items():
        if key in locked_entity_keys or f"entities.{key}" in (deterministic.locked_fields or {}):
            if value != entities.get(key):
                rejected.append(f"locked_field_change_rejected:entities.{key}")
            continue
        if key not in entities or entities[key] in (None, "", [], {}):
            # Only concrete observed values. A category such as "suspicious DNS" or
            # "algorithmically generated domains" is an investigation topic, not an
            # entity, and recording it as one would fabricate an observation.
            if not _is_concrete_entity(value):
                if "entity_not_concrete" not in rejected:
                    rejected.append("entity_not_concrete")
                continue
            # Unresolved referents and other unsupplied names are not observations.
            if not _entity_value_grounded(query, deterministic, value):
                if "unresolved_referent_not_entity" not in rejected:
                    rejected.append("unresolved_referent_not_entity")
                continue
            entities[key] = value
            field_sources["entities"] = "semantic_t4"
            accepted_any = True

    time_scope = deterministic.time_scope
    if "time_scope" in (deterministic.locked_fields or {}) and proposal.time_scope:
        if proposal.time_scope != deterministic.time_scope:
            rejected.append("locked_field_change_rejected:time_scope")
    elif time_scope in (None, "") and proposal.time_scope:
        # A silent default ("last 24 hours") would narrow an investigation the
        # analyst never scoped. Operational defaults belong to a later governed
        # stage, not to semantic understanding.
        if _time_scope_grounded(query, proposal.time_scope):
            time_scope = proposal.time_scope
            field_sources["time_scope"] = "semantic_t4"
            accepted_any = True
        else:
            rejected.append("time_scope_not_grounded_in_query")

    evidence = list(deterministic.evidence_requirements)
    for item in proposal.evidence_requirements:
        if item and item not in evidence:
            evidence.append(item)
            field_sources["evidence_requirements"] = "semantic_t4"
            accepted_any = True

    hypotheses = list(deterministic.competing_hypotheses)
    for item in proposal.competing_hypotheses:
        if item and item not in hypotheses:
            hypotheses.append(item)
            field_sources["competing_hypotheses"] = "semantic_t4"
            accepted_any = True

    if clarification_required and not clarification_reason:
        clarification_reason = deterministic.clarification_reason or "semantic_t4_clarification"

    family_required, family_prohibited = capabilities_for_intent_family(intent_family)
    required = set(family_required) | set(deterministic.required_capabilities)
    prohibited = set(family_prohibited) | set(deterministic.prohibited_capabilities)
    locked_prohibitions = (deterministic.locked_fields or {}).get("prohibited_capabilities") or []
    prohibited |= {str(item) for item in locked_prohibitions}
    prohibited -= set(deterministic.required_capabilities)
    required -= prohibited - set(deterministic.required_capabilities)

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
            "competing_hypotheses": hypotheses,
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
                    # Diagnostics only: what the model offered vs what deterministic
                    # validation kept. Never read by routing, planning or policy.
                    "proposed_fields": _proposed_field_names(proposal),
                    "accepted_fields": sorted(
                        name for name, src in field_sources.items() if src == "semantic_t4"
                    ),
                    "semantic_confidence": proposal.semantic_confidence,
                },
            },
        }
    )
    return merged


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
    from app.llm.policy.candidates import candidate_t4_response_schema, live_system_prompt

    result = client.generate(
        system_prompt=live_system_prompt("semantic_t4", _SEMANTIC_T4_SYSTEM_PROMPT),
        user_prompt=_build_semantic_t4_user_prompt(query, deterministic),
        # 400 tokens at the measured 4.1-4.5 tok/s is ~90s of generation alone,
        # which is most of the 120s VPS remediation budget (C2/C3 measurements).
        # The proposal schema fits comfortably below this cap; a truncated payload
        # is rejected by the parser rather than half-accepted.
        max_tokens=220,
        temperature=0.1,
        # Constrained decoding where the serving stack supports it (C2 measured the
        # unconstrained call returning prose). Servers that ignore the field are
        # unaffected — the parser still validates the payload.
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "semantic_t4_proposal",
                # Full SemanticT4Proposal schema on ABSTAIN — not the legacy
                # unresolved-field patch subset. Returned unchanged outside the
                # P8 candidate eval arm; production decoding is untouched.
                "schema": candidate_t4_response_schema(_SEMANTIC_T4_SCHEMA),
            },
        },
        timeout_seconds=timeout,
    )
    return result.text
