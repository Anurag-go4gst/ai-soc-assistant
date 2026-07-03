"""LLM-assisted resource planning for unmatched questions (T0.5).

For queries the deterministic registries cannot place (`out_of_registry`,
`near_105_question`), a local model may PROPOSE a resource plan as data:
steps referencing registry resource ids only. Every step is then validated
deterministically; invalid steps are dropped with recorded reasons. The
model never executes anything, never sees raw events, and a failed or empty
proposal falls back to the deterministic plan exactly as if the bridge did
not exist.

Gating: both existing flags must be on — the intent-advisor flag (LLM may
advise on intake) and the live-synthesis flag (a live client is wired).
Pinned eval/test runtimes set live synthesis off, so gates stay LLM-free.

Live promotion (item 1.3): `apply_llm_primary_resource_plan` in
`plan_promotion_merge.py` calls this bridge inline during
`graph_node_evidence_planning` when control plane + bridge flags are on.
The finalize-stage shadow trace reuses the promoted plan without a second
LLM call (`promoted_inline`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.llm.adapter.output_preprocessor import BRIDGE_PROPOSAL_SCHEMA, preprocess_llm_output
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_registry import (
    ResourceDescriptor,
    ResourceRegistry,
    is_composer_dispatchable,
    load_resource_registry,
    registry_dispatch_mode,
)

_TRIGGER_MATCH_PATHS = {"out_of_registry", "near_105_question"}
_BRIDGE_TIMEOUT_SECONDS = 20.0
_DISPATCHABLE_AVAILABILITY = frozenset({"available", "fixture_only"})
_ALLOWED_PURPOSES = {"knowledge_retrieval", "spl_artifact", "mcp_execution", "mitre_mapping", "cve_lookup", "narration"}
_DEFERRED_PURPOSES = frozenset({"action_proposal"})
_TIME_BOUND = re.compile(r"^(now|-?\d+[smhd](@[smhd])?)$")
# Raw query text must never ride in a proposal — plans bind families/corpora,
# never SPL strings.
_FORBIDDEN_ARG_KEYS = {"spl", "search_query", "query", "raw_spl", "search"}

_SYSTEM_PROMPT = (
    "You are a SOC investigation planner. Given an analyst question, propose "
    "an ordered resource plan as ONE JSON object and nothing else:\n"
    '{"steps": [{"resource_id": "<id from the catalog>", "purpose": '
    '"<knowledge_retrieval|spl_artifact|mcp_execution|mitre_mapping|cve_lookup|narration>", '
    '"args": {}}], "rationale": "<one sentence>"}\n'
    "Rules: use only resource ids from the catalog provided; never invent ids; "
    "never include SPL text or raw queries in args; prefer the cheapest "
    "resource that answers the question. "
    "Use skill:cve_lookup with purpose cve_lookup for CVE/KEV/patch-gap questions "
    "(snapshot read-only). Use skill:mitre_mapping with purpose mitre_mapping when "
    "the analyst asks for ATT&CK technique mapping with alert or log context."
)


# The bridge is an inline pre-answer step on the live path; it must never
# consume the narration-sized timeout budget. On expiry the deterministic
# plan stands — so a tight cap costs only provenance, never correctness.
_BRIDGE_TIMEOUT_SECONDS_CAP = 20


@dataclass(frozen=True)
class PlanPromotionResult:
    plan: ResourcePlan | None
    llm_bridge: str
    dropped_steps: list[dict[str, str]] = field(default_factory=list)


def validate_llm_plan_proposal(
    payload: dict[str, Any],
    *,
    registry: ResourceRegistry,
    mcp_allowed: bool,
    action_mode: str | None = None,
    match_path: str | None = None,
) -> PlanPromotionResult:
    """Validate an LLM plan proposal and emit promotion provenance."""
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        return PlanPromotionResult(plan=None, llm_bridge="rejected:invalid_payload")

    steps: list[PlanStep] = []
    dropped: list[dict[str, str]] = []
    for index, raw in enumerate(raw_steps[:8]):
        if not isinstance(raw, dict):
            dropped.append({"step": str(index), "reason": "step_not_object"})
            continue
        resource_id = str(raw.get("resource_id") or "")
        purpose = str(raw.get("purpose") or "")
        verdict = _step_verdict(
            resource_id, purpose, raw.get("args"), registry=registry, mcp_allowed=mcp_allowed
        )
        if verdict is not None:
            dropped.append({"step": resource_id or str(index), "reason": verdict})
            continue
        steps.append(
            PlanStep(
                step_id=f"llm_{index}",
                resource_id=resource_id,
                purpose=purpose,
                args_template=_clean_args(raw.get("args")),
                policy_checks=["llm_proposed_deterministically_validated"],
            )
        )

    if not steps:
        reason = "rejected:all_steps_dropped"
        if dropped and all(item.get("reason") == "unknown_resource_id" for item in dropped):
            reason = "rejected:unknown_resource_id"
        return PlanPromotionResult(plan=None, llm_bridge=reason, dropped_steps=dropped)

    return PlanPromotionResult(
        plan=ResourcePlan(
            steps=steps,
            plan_source="llm_proposed_validated",
            provenance={
                "bridge": "llm_plan_bridge_v1",
                "llm_bridge": "promoted",
                "match_path": match_path,
                "action_mode": action_mode,
                "rationale": str(payload.get("rationale") or "")[:300],
                "dropped_steps": dropped,
            },
        ),
        llm_bridge="promoted",
        dropped_steps=dropped,
    )


def _bridge_client() -> Any | None:
    from app.llm.clients.endpoint_resolver import build_failover_chat_client
    from app.llm.clients.failover_client import FailoverChatClient
    from app.llm.clients.local_chat_client import LocalChatClient

    client = build_failover_chat_client(role=None, sidecar=True)
    if client is None:
        return None
    capped_chain: list[tuple[str, LocalChatClient]] = []
    for label, member in client.chain:
        capped_chain.append(
            (
                label,
                LocalChatClient(
                    base_url=member.base_url,
                    model=member.model,
                    api_key=getattr(member, "api_key", ""),
                    timeout_seconds=min(int(member.timeout_seconds), _BRIDGE_TIMEOUT_SECONDS_CAP),
                ),
            )
        )
    return FailoverChatClient(chain=tuple(capped_chain))


def bridge_trigger_match(match_path: str | None) -> bool:
    """True when the intake path is one the bridge may plan for."""
    return str(match_path or "") in _TRIGGER_MATCH_PATHS


def bridge_enabled() -> bool:
    return bool(
        settings.ai_soc_llm_intent_advisor_enabled
        and settings.ai_soc_llm_live_synthesis_enabled
    )


def propose_validated_llm_plan(
    *,
    query: str,
    match_path: str | None,
    action_mode: str | None,
    mcp_allowed: bool,
    client: Any | None = None,
    registry: ResourceRegistry | None = None,
    require_bridge_flags: bool = True,
) -> ResourcePlan | None:
    """Return a validated LLM-proposed plan, or None (caller keeps deterministic)."""
    if str(match_path or "") not in _TRIGGER_MATCH_PATHS:
        return None
    if require_bridge_flags and not bridge_enabled():
        return None
    try:
        registry = registry or load_resource_registry()
        if client is None:
            client = _bridge_client()
        if client is None:
            return None
        # Wall-clock bound: this runs on the finalize path; a hung endpoint must not
        # block the request (the PowerGrid latency lesson). Mirrors sidecar timeout.
        from app.llm.sidecar_governance import run_sidecar_llm_with_timeout

        def _generate() -> str:
            return getattr(
                client.generate(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=_user_prompt(query, registry),
                    max_tokens=400,
                    temperature=0.1,
                ),
                "text",
                "",
            )

        call = run_sidecar_llm_with_timeout(_generate, timeout_seconds=_BRIDGE_TIMEOUT_SECONDS)
        raw_text = call.raw_output
        if call.timed_out or not isinstance(raw_text, str) or not raw_text.strip():
            return None
        pre = preprocess_llm_output(raw_text, BRIDGE_PROPOSAL_SCHEMA, allow_retry=False)
        if pre.payload is None:
            return None
        promotion = validate_llm_plan_proposal(
            pre.payload,
            registry=registry,
            mcp_allowed=mcp_allowed,
            action_mode=action_mode,
            match_path=match_path,
        )
        if promotion.plan is None:
            return None
        provenance = dict(promotion.plan.provenance)
        provenance["llm_output_utilization"] = pre.llm_output_utilization
        if pre.repairs:
            provenance["preprocessor_repairs"] = pre.repairs
        return promotion.plan.model_copy(update={"provenance": provenance})
    except Exception:
        # Any failure means: behave exactly as if the bridge does not exist.
        return None


def _user_prompt(query: str, registry: ResourceRegistry) -> str:
    catalog = [
        {"resource_id": item.resource_id, "capabilities": item.capabilities}
        for item in registry.resources
        if item.availability in {"available", "fixture_only"} and item.policy_tier <= 1
    ]
    return json.dumps({"question": query, "catalog": catalog}, ensure_ascii=False)


def _validate_proposal(
    payload: dict[str, Any],
    *,
    registry: ResourceRegistry,
    mcp_allowed: bool,
    action_mode: str | None,
    match_path: str | None,
) -> ResourcePlan | None:
    return validate_llm_plan_proposal(
        payload,
        registry=registry,
        mcp_allowed=mcp_allowed,
        action_mode=action_mode,
        match_path=match_path,
    ).plan


def _step_verdict(
    resource_id: str,
    purpose: str,
    args: Any,
    *,
    registry: ResourceRegistry,
    mcp_allowed: bool,
) -> str | None:
    """Return a drop reason, or None when the step is acceptable."""
    if purpose in _DEFERRED_PURPOSES:
        return "unknown_purpose"
    descriptor = registry.by_id(resource_id)
    if descriptor is None:
        return "unknown_resource_id"
    if descriptor.availability == "blocked":
        return "resource_blocked"
    if not is_composer_dispatchable(descriptor, mode=registry_dispatch_mode()):
        return "resource_not_dispatchable"
    if purpose not in _ALLOWED_PURPOSES:
        return "unknown_purpose"
    if not _purpose_allowed_for_resource(descriptor, purpose):
        return "purpose_not_allowed_for_resource"
    if purpose == "mcp_execution" or descriptor.kind == "mcp_tool":
        if not mcp_allowed:
            return "mcp_not_allowed_for_intent"
        if descriptor.policy_tier > 2:
            return "policy_tier_exceeded"
    elif descriptor.policy_tier > 1:
        return "policy_tier_exceeded"
    if isinstance(args, dict):
        for key, value in args.items():
            if str(key).lower() in _FORBIDDEN_ARG_KEYS:
                return "raw_query_args_not_accepted"
            if str(key) in {"earliest_time", "latest_time"} and not _TIME_BOUND.match(str(value)):
                return "unbounded_time_window"
    return None


def _purpose_allowed_for_resource(descriptor: ResourceDescriptor, purpose: str) -> bool:
    if purpose == "knowledge_retrieval":
        return descriptor.kind == "rag_corpus"
    if purpose == "spl_artifact":
        return descriptor.kind in {"spl_template_family", "spl_lab_draft_family", "skill"}
    if purpose == "mitre_mapping":
        return descriptor.resource_id == "skill:mitre_mapping"
    if purpose == "cve_lookup":
        return descriptor.resource_id == "skill:cve_lookup"
    if purpose == "mcp_execution":
        return descriptor.kind == "mcp_tool"
    if purpose == "narration":
        return descriptor.kind == "llm_role"
    return False


def _clean_args(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        return {}
    return {
        str(key): value
        for key, value in args.items()
        if str(key).lower() not in _FORBIDDEN_ARG_KEYS
    }
