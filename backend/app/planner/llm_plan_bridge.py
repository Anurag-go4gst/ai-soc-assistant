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
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.llm.adapter.json_extractor import extract_first_json_object
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_registry import ResourceRegistry, load_resource_registry

_TRIGGER_MATCH_PATHS = {"out_of_registry", "near_105_question"}
_ALLOWED_PURPOSES = {"knowledge_retrieval", "spl_artifact", "mcp_execution", "mitre_mapping", "narration"}
_TIME_BOUND = re.compile(r"^(now|-?\d+[smhd](@[smhd])?)$")
# Raw query text must never ride in a proposal — plans bind families/corpora,
# never SPL strings.
_FORBIDDEN_ARG_KEYS = {"spl", "search_query", "query", "raw_spl", "search"}

_SYSTEM_PROMPT = (
    "You are a SOC investigation planner. Given an analyst question, propose "
    "an ordered resource plan as ONE JSON object and nothing else:\n"
    '{"steps": [{"resource_id": "<id from the catalog>", "purpose": '
    '"<knowledge_retrieval|spl_artifact|mitre_mapping|narration>", '
    '"args": {}}], "rationale": "<one sentence>"}\n'
    "Rules: use only resource ids from the catalog provided; never invent ids; "
    "never include SPL text or raw queries in args; prefer the cheapest "
    "resource that answers the question."
)


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
) -> ResourcePlan | None:
    """Return a validated LLM-proposed plan, or None (caller keeps deterministic)."""
    if str(match_path or "") not in _TRIGGER_MATCH_PATHS:
        return None
    if not bridge_enabled():
        return None
    try:
        registry = registry or load_resource_registry()
        if client is None:
            from app.llm.clients.local_chat_client import build_synthesis_client_from_settings

            client = build_synthesis_client_from_settings()
        if client is None:
            return None
        result = client.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_user_prompt(query, registry),
            max_tokens=400,
            temperature=0.1,
        )
        raw_text = getattr(result, "text", None)
        if not isinstance(raw_text, str) or not raw_text.strip():
            return None
        extraction = extract_first_json_object(raw_text)
        if not extraction.parsed_ok or not isinstance(extraction.payload, dict):
            return None
        return _validate_proposal(
            extraction.payload,
            registry=registry,
            mcp_allowed=mcp_allowed,
            action_mode=action_mode,
            match_path=match_path,
        )
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
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        return None

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
        return None
    return ResourcePlan(
        steps=steps,
        plan_source="llm_proposed_validated",
        provenance={
            "bridge": "llm_plan_bridge_v1",
            "match_path": match_path,
            "action_mode": action_mode,
            "rationale": str(payload.get("rationale") or "")[:300],
            "dropped_steps": dropped,
        },
    )


def _step_verdict(
    resource_id: str,
    purpose: str,
    args: Any,
    *,
    registry: ResourceRegistry,
    mcp_allowed: bool,
) -> str | None:
    """Return a drop reason, or None when the step is acceptable."""
    descriptor = registry.by_id(resource_id)
    if descriptor is None:
        return "unknown_resource_id"
    if descriptor.availability == "blocked":
        return "resource_blocked"
    if purpose not in _ALLOWED_PURPOSES:
        return "unknown_purpose"
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


def _clean_args(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        return {}
    return {
        str(key): value
        for key, value in args.items()
        if str(key).lower() not in _FORBIDDEN_ARG_KEYS
    }
