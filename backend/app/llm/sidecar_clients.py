"""Production sidecar LLM invocation with role resolution, failover, and timeouts."""

from __future__ import annotations

import json
from typing import Any, Callable

from app.config import settings
from app.llm.clients.endpoint_resolver import build_failover_chat_client
from app.llm.clients.failover_client import FailoverChatClient
from app.llm.prompts import (
    AUTHORITY_HIERARCHY_RULES,
    PROMPT_CONTRACTS,
    REVIEW_ONLY_SAFETY_RULES,
)
from app.llm.sidecar_governance import (
    REASONING_REJECTION_MATCHING,
    resolve_sidecar_role_status,
    run_sidecar_llm_with_timeout,
)

INTENT_ROLE = "intent_shadow_classifier"
MISSING_EVIDENCE_ROLE = "missing_evidence_reasoner"

# Role wrapper timeouts. Aligned with the endpoint_resolver sidecar socket ceiling
# (SIDECAR_SOCKET_CEILING_SECONDS = 120) so the wrapper never abandons a call the
# socket would have completed — a single-slot 8B instruct answers in ~30-90s.
# Keep wrapper >= the socket the call will use; both are bounded by env
# AI_SOC_LLM_TIMEOUT_SECONDS. Do not lower these below the model's real latency.
_ROLE_TIMEOUT_SECONDS: dict[str, float] = {
    INTENT_ROLE: 120.0,
    MISSING_EVIDENCE_ROLE: 120.0,
    "route_plan_candidate_generator": 120.0,
    "spl_advisory_generator": 120.0,
    "mitre_candidate_mapper": 120.0,
    "mitre_reasoner": 120.0,
    "template_match_semantic_assist": 90.0,
    "template_render_parameter_assist": 90.0,
    "governed_composer": 120.0,
    "guided_investigation_plan_proposer": 15.0,
}

# Failover hop (Instruct retry after primary timeout) — give it enough to complete
# on a slow single-slot model, not the old 20s that guaranteed a second timeout.
_FAILOVER_HOP_TIMEOUT_SECONDS = 90.0


def _instruct_failover_client(client: FailoverChatClient) -> FailoverChatClient | None:
    """On primary timeout, retry Instruct only — not the full remaining chain."""
    instruct_hops = tuple(
        (label, hop) for label, hop in client.chain if label == "foundation_sec_instruct_fallback"
    )
    if instruct_hops:
        return FailoverChatClient(chain=instruct_hops)
    if len(client.chain) > 1:
        return FailoverChatClient(chain=client.chain[1:])
    return None


def sidecar_timeout_seconds(role: str) -> float:
    return _ROLE_TIMEOUT_SECONDS.get(role, 15.0)


def build_failover_client_for_role(role: str) -> FailoverChatClient | None:
    """Build a failover client for a sidecar role honoring governance ``enabled``."""
    role_status = resolve_sidecar_role_status(
        role,
        reasoning_rejection_reason=REASONING_REJECTION_MATCHING,
        assist_invoked=False,
    )
    if role_status.role_configured and not role_status.enabled:
        return None
    return build_failover_chat_client(role=role, sidecar=True)


def _contract_for_role(role: str) -> dict[str, Any]:
    return PROMPT_CONTRACTS.get(role) or {}


def _system_prompt_for_role(role: str, system_prompt: str | None) -> str:
    system = system_prompt or str(_contract_for_role(role).get("system_instruction") or "").strip()
    if not system:
        system = "Return JSON only. Do not add markdown."
    return system


def _build_callable_for_client(
    *,
    client: FailoverChatClient,
    role: str,
    user_prompt: str,
    system_prompt: str | None,
    max_tokens: int,
    temperature: float | None,
    answered_label_holder: list[str | None],
) -> Callable[[], str]:
    system = _system_prompt_for_role(role, system_prompt)
    temp = (
        float(temperature)
        if temperature is not None
        else float(settings.ai_soc_llm_temperature or 0.1)
    )

    def _call() -> str:
        result = client.generate(
            system_prompt=system,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temp,
        )
        answered_label_holder[0] = result.answered_label or None
        return result.text

    return _call


def build_sidecar_raw_provider(
    *,
    role: str,
    user_prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 800,
    temperature: float | None = None,
) -> Callable[[], str] | None:
    """Return a callable that performs a failover-backed sidecar completion."""
    if settings.ai_soc_llm_mode.strip().lower() in {"mock", "disabled", ""}:
        return None
    if not settings.ai_soc_llm_enabled:
        return None

    client = build_failover_client_for_role(role)
    if client is None:
        return None

    answered_label_holder: list[str | None] = [None]
    return _build_callable_for_client(
        client=client,
        role=role,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        answered_label_holder=answered_label_holder,
    )


def invoke_sidecar_role(
    *,
    role: str,
    user_prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 800,
    timeout_seconds: float | None = None,
    temperature: float | None = None,
    allow_failover: bool = True,
) -> tuple[str | None, bool, str | None]:
    """Invoke a sidecar role; returns (raw_output, timed_out, answered_label)."""
    if settings.ai_soc_llm_mode.strip().lower() in {"mock", "disabled", ""}:
        return None, False, None
    if not settings.ai_soc_llm_enabled:
        return None, False, None

    client = build_failover_client_for_role(role)
    if client is None:
        return None, False, None

    timeout = timeout_seconds if timeout_seconds is not None else sidecar_timeout_seconds(role)
    answered_label_holder: list[str | None] = [None]
    provider = _build_callable_for_client(
        client=client,
        role=role,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        answered_label_holder=answered_label_holder,
    )
    call = run_sidecar_llm_with_timeout(provider, timeout_seconds=timeout)
    if not call.timed_out:
        return call.raw_output, False, answered_label_holder[0]

    if allow_failover and len(client.chain) > 1:
        fallback_client = _instruct_failover_client(client)
        if fallback_client is None:
            return None, True, None
        hop_timeout = min(timeout, _FAILOVER_HOP_TIMEOUT_SECONDS)
        # Fresh holder: the primary call was orphaned on timeout and may still
        # be running; it must not clobber the fallback's answered_label. The
        # model-slot guard in run_sidecar_llm_with_timeout keeps the fallback from
        # piling onto the slot while that orphan still holds it (skips instead).
        fallback_label_holder: list[str | None] = [None]
        fallback_provider = _build_callable_for_client(
            client=fallback_client,
            role=role,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            answered_label_holder=fallback_label_holder,
        )
        fallback_call = run_sidecar_llm_with_timeout(
            fallback_provider,
            timeout_seconds=hop_timeout,
        )
        if not fallback_call.timed_out and fallback_call.raw_output:
            return fallback_call.raw_output, False, fallback_label_holder[0]
        return None, True, None

    return None, True, None


def build_intent_advisory_prompt(
    *,
    query: str,
    context_block: str,
) -> str:
    schema = {
        "intent_family_candidate": "",
        "path_type_candidate": "",
        "question_ref_candidate": "",
        "use_case_id_candidate": "",
        "paraphrase_detected": False,
        "ambiguity_reasons": [],
        "clarification_draft": None,
        "evidence_need_hints": [],
        "entity_slots_candidate": {},
        "entity_slot_confidence": {},
        "entity_slot_reasons": {},
        "confidence_metadata": {"confidence": 0.0},
        "spl_authoring_request": False,
        "requires_source_profile": None,
    }
    instructions = (
        "Extract entity_slots_candidate only for values explicitly present or strongly implied "
        "in the analyst query. Do NOT invent indexes, sourcetypes, IPs, hosts, users, lookups, "
        "asset names, or time windows. Supported slot keys include: index, indexes, sourcetype, "
        "host, user, src_ip, dest_ip, cidr, port, service, protocol, event_code, function_code, "
        "action_semantic, threshold, time_window, lookup, src_zone, dest_zone, "
        "src_scope, dest_scope, aggregation_subject, unexpected_ip_direction, allowlist_semantic. "
        "Use canonical slot names: event_id/eventid -> event_code, account/username -> user, "
        "src_subnet/source_subnet -> src_scope, dest_subnet/destination_subnet -> dest_scope."
    )
    authority = "Authority hierarchy:\n" + "\n".join(
        f"- {rule}" for rule in AUTHORITY_HIERARCHY_RULES
    )
    safety = "Review-only safety:\n" + "\n".join(
        f"- {rule}" for rule in REVIEW_ONLY_SAFETY_RULES
    )
    few_shots = (
        "Few-shot coverage hints (copy the pattern, not the literal values):\n"
        "- Windows failed logins: `Which users have excessive failed logins?` -> "
        "authentication evidence, aggregate by user, no invented source profile.\n"
        "- Off-shift logon: `Find Event 4624 logons after 10 PM` -> event_code=4624 "
        "and time_window/after-hours hint; do not treat the date or hour as a host.\n"
        "- Cisco ASA IOC lookup: `Check Cisco ASA hits to known bad IPs` -> firewall/network "
        "evidence and lookup/IOC hints only when supplied; do not pivot to asset inventory.\n"
        "- SCADA threshold anomaly: `Show SCADA threshold anomalies` -> OT/SCADA source "
        "and threshold/function-code hints; do not recast as authentication logs.\n"
        "- SMB top talkers: `Which hosts have most SMB traffic?` -> network traffic "
        "aggregation by the requested host/src/dest entity; no lateral-movement claim.\n"
        "- Conceptual knowledge: `Explain MITRE T1021.002` -> knowledge recall; no SPL "
        "or live-result claim.\n"
        "- Unsafe containment: `Block the source IP` -> human-review/unsafe-action hint; "
        "never authorize block, isolate, disable, contain, or execute.\n"
        "- Ambiguous investigation: `Investigate this alert` with no context -> clarification.\n"
        "- Universal SPL authoring: `Without using any company template, write a universal SPL block "
        "to extract hour and day of week and filter weekends.` -> spl_generation_only, "
        "spl_authoring_request=true, requires_source_profile=false; review-only SPL text, no live investigation."
    )
    return (
        f"{context_block}\n\n"
        f"Analyst query:\n{query}\n\n"
        f"{instructions}\n\n"
        f"{authority}\n\n"
        f"{safety}\n\n"
        f"{few_shots}\n\n"
        "Return ONE JSON object matching this shape (no markdown):\n"
        f"{json.dumps(schema, indent=2)}"
    )
