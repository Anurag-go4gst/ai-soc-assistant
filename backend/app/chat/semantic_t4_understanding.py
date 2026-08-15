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
from typing import Any, get_args

from pydantic import ValidationError

from app.chat.contracts.intent_classification import IntentFamily
from app.chat.contracts.resolved_query import (
    ALLOWED_CAPABILITIES,
    AmbiguityState,
    ResolvedQueryContract,
)
from app.chat.contracts.semantic_t4_proposal import SemanticT4Proposal
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


_SEMANTIC_T4_SYSTEM_PROMPT = (
    "You complete SOC query understanding. Resolve only the unresolved semantic meaning.\n"
    "Rules:\n"
    "- Do not rewrite locked fields; repeat them unchanged.\n"
    "- Preserve competing hypotheses; do not classify something malicious prematurely.\n"
    "- Set clarification_required=true only when the query points at something that was not\n"
    "  supplied — an unnamed event, host, alert or indicator. A broad hunting request is not\n"
    "  missing context: resolve it and list what evidence would answer it.\n"
    "- Never invent facts that were not supplied.\n"
    "- Do not select a skill or route. Do not generate or execute SPL. Do not call MCP.\n"
    "- Do not make RBAC, HIL or policy decisions.\n"
    "- Return one JSON object only: the resolved fields themselves. Do not repeat the input,\n"
    "  do not wrap the answer in another key, no markdown, no prose."
)

# Compact, curated. Prompt assets — not a retrieval system and not an agent.
_SEMANTIC_T4_FEW_SHOT: tuple[dict[str, Any], ...] = (
    # A — hypothesis and evidence: name the objective, keep lateral movement a
    # hypothesis rather than a finding, state what evidence would settle it.
    {
        "query": "repeated failed admin logons on a server then one that succeeded",
        "unresolved": ["normalized_goal", "evidence_requirements"],
        "output": {
            "normalized_goal": "determine whether the successful admin logon after repeated "
            "failures represents account compromise",
            "ambiguity_state": "unambiguous",
            "clarification_required": False,
            "evidence_requirements": [
                "failure-then-success sequence for that account and source",
                "whether the source host normally authenticates to this server",
                "subsequent authentications from the same account to other hosts "
                "(lateral movement remains a hypothesis, not a finding)",
            ],
            "confidence": 0.6,
        },
    },
    # B — competing hypotheses: benign and malicious both stay on the table.
    {
        "query": "powershell running on a few endpoints with outbound dns to new domains",
        "unresolved": ["normalized_goal", "evidence_requirements"],
        "output": {
            "normalized_goal": "assess whether scripted activity with new-domain lookups is "
            "malicious or routine administration",
            "ambiguity_state": "unambiguous",
            "clarification_required": False,
            "evidence_requirements": [
                "parent process and command line for the PowerShell activity",
                "domain registration age and query cadence",
                "competing explanation: software updater, admin script or telemetry",
            ],
            "confidence": 0.5,
        },
    },
    # C — clarification: the referenced event is not available, so ask.
    {
        "query": "compare this with what happened last week and tell me if it is getting worse",
        "unresolved": ["entities", "time_scope", "clarification_required"],
        "output": {
            "normalized_goal": "compare a prior event with a current one the analyst has not named",
            "ambiguity_state": "clarification_required",
            "clarification_required": True,
            "clarification_reason": "which event does 'this' refer to, and which prior "
            "time range should it be compared against",
            "confidence": 0.3,
        },
    },
)


_UNRESOLVED_TO_SCHEMA: dict[str, str] = {
    "semantic_goal": "normalized_goal",
    "investigation_target": "entities",
}


def _job_aware_unresolved_schema_names(deterministic: ResolvedQueryContract) -> list[str]:
    names: list[str] = []
    for field in deterministic.unresolved_fields or ["semantic_goal"]:
        names.append(_UNRESOLVED_TO_SCHEMA.get(field, field))
    if "normalized_goal" not in names and "semantic_goal" in (deterministic.unresolved_fields or []):
        names.append("normalized_goal")
    # Clarification is always proposable; it cannot clear a locked deterministic ask.
    if "clarification_required" not in (deterministic.locked_fields or {}):
        names.extend(["ambiguity_state", "clarification_required", "clarification_reason"])
    names.append("confidence")
    # Never offer locked authority or derived capability grants as T4 schema keys.
    blocked = {
        "intent_family",
        "answer_goal",
        "required_capabilities",
        "prohibited_capabilities",
        *list(deterministic.locked_fields or {}),
    }
    return [name for name in names if name not in blocked]


def _schema_limited_to_unresolved(deterministic: ResolvedQueryContract) -> dict[str, Any]:
    allowed = set(_job_aware_unresolved_schema_names(deterministic))
    properties = {
        key: value
        for key, value in _SEMANTIC_T4_SCHEMA["properties"].items()
        if key in allowed
    }
    return {"type": "object", "properties": properties}


def _build_semantic_t4_user_prompt(query: str, deterministic: ResolvedQueryContract) -> str:
    """Unresolved fragment + locked map + allowed vocabulary + strict unresolved schema."""
    locked = dict(deterministic.locked_fields or {})
    if not locked:
        locked = {
            "intent_family": deterministic.intent_family,
            "answer_goal": deterministic.answer_goal,
            "prohibited_capabilities": sorted(deterministic.prohibited_capabilities),
        }
    unresolved = _job_aware_unresolved_schema_names(deterministic)
    example_lines: list[str] = []
    for index, example in enumerate(_SEMANTIC_T4_FEW_SHOT, start=1):
        example_lines.append(f"EXAMPLE {index} QUERY: {example['query']}")
        example_lines.append(
            f"EXAMPLE {index} ANSWER: {json.dumps(example['output'], separators=(',', ':'))}"
        )
    task = json.dumps(
        {
            "query": query,
            "unresolved_query_fragment": query,
            "locked_fields_do_not_change": locked,
            "unresolved_fields_to_resolve": unresolved,
            "allowed_values": {"ambiguity_state": sorted(_AMBIGUITY_RANK)},
        },
        separators=(",", ":"),
    )
    return "\n".join([*example_lines, f"TASK: {task}", "ANSWER:"])


def _permits_t4_call(deterministic: ResolvedQueryContract) -> bool:
    sufficiency = deterministic.understanding_sufficiency or {}
    return str(sufficiency.get("next_action") or "") == "CALL_T4"


def maybe_enrich_t4_semantic(
    deterministic: ResolvedQueryContract,
    *,
    query: str,
    raw_output_provider: SemanticRawProvider | None = None,
) -> ResolvedQueryContract:
    """Return deterministic contract unless T4 + flag-on + CALL_T4 + a valid bounded hop."""
    if not settings.ai_soc_t4_semantic_understanding_enabled:
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
        return _with_semantic_trace(prepared, {**base_trace, "rejected_reasons": [reason]})

    proposal, parse_reason = _parse_proposal(call.raw_output)
    if proposal is None:
        return _with_semantic_trace(
            prepared, {**base_trace, "rejected_reasons": [parse_reason or "schema_invalid"]}
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


def _is_concrete_entity(value: Any) -> bool:
    text = str(value).strip()
    if not text or len(text.split()) > 3:
        return False
    return bool(_CONCRETE_ENTITY_RE.search(text))


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


def _merge_proposal(
    deterministic: ResolvedQueryContract,
    proposal: SemanticT4Proposal,
    base_trace: dict[str, Any],
    *,
    query: str,
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
        # Three kinds of uncertainty are not interchangeable. Only *semantic*
        # uncertainty — an unresolved referent — may become an analyst question.
        # Missing evidence, thresholds or detection criteria are investigation
        # inputs, and a model that confuses them must not be able to turn a clear
        # hunt into a clarification prompt. Deterministic, so it holds whatever the
        # prompt or the model does.
        if _has_unresolved_referent(query):
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
            # Escalating to `clarification_required` is the same act as asking the
            # analyst a question, so it answers to the same rule: only an unresolved
            # referent qualifies. Otherwise this is evidence uncertainty wearing a
            # different field name.
            if (
                proposal.ambiguity_state == "clarification_required"
                and not _has_unresolved_referent(query)
            ):
                if "clarification_without_unresolved_referent" not in rejected:
                    rejected.append("clarification_without_unresolved_referent")
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
        system_prompt=_SEMANTIC_T4_SYSTEM_PROMPT,
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
                "schema": _schema_limited_to_unresolved(deterministic),
            },
        },
        timeout_seconds=timeout,
    )
    return result.text
