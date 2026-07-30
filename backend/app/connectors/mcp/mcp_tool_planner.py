"""LLM-proposed, deterministically-reviewed MCP tool-call planner.

Flow (advisory; planning only, no live MCP I/O):

    build calibrated prompt (closed tool set + produces/preconditions + few-shot)
      -> Foundation-Sec Instruct (response_format=json_object)        [primary]
      -> optional Qwen failover (flag AI_SOC_LLM_PLANNER_QWEN_FAILOVER_ENABLED)
      -> parse JSON tool list
      -> review_proposed_tool_chronology() validates against the playbook
      -> on ANY failure (no endpoint / transport / parse / empty): deterministic default

The LLM only *proposes*; the deterministic reviewer is final authority and the
deterministic default carries when the model is unavailable or invalid.

1-LLM decision (2026-06-15): Instruct is the planner; Qwen is OFF by default and
only appended as a failover after Instruct when the flag is enabled and the
QWEN_* endpoint is configured.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.connectors.mcp.mcp_tool_chronology import (
    ChronologyPlan,
    load_playbook,
    review_proposed_tool_chronology,
)
from app.llm.clients.endpoint_resolver import (
    TRANSPORT_SYNTHESIS,
    _append_endpoint,
    resolve_foundation_sec_instruct_endpoint,
    resolve_local_primary_endpoint,
    resolve_qwen_primary_endpoint,
)
from app.llm.clients.failover_client import FailoverChatClient
from app.llm.clients.local_chat_client import LocalChatClient, LocalChatError

logger = logging.getLogger(__name__)

PLANNER_MAX_TOKENS = 400
PLANNER_TEMPERATURE = 0.1
PLANNER_RESPONSE_FORMAT = {"type": "json_object"}


def build_planner_client() -> FailoverChatClient | None:
    """Planner chain: Instruct (local primary) → [Qwen failover if flag] → Instruct fallback.

    Unlike the generic failover chain, Qwen is NOT primary here — Instruct leads,
    Qwen is only appended (after Instruct) when the planner flag is enabled.
    """
    # sidecar=False on purpose: the planner is an advisory/off-blocking-path step,
    # not a live-chat sidecar, so it must NOT inherit the 120s sidecar socket cap.
    # It gets the full AI_SOC_LLM_TIMEOUT_SECONDS, letting a slow local model
    # actually return a plan when invoked async (eval/precompute). Never wire this
    # onto the live /chat blocking path.
    chain: list[tuple[str, LocalChatClient]] = []
    build_fps: list = []
    transport_mode = TRANSPORT_SYNTHESIS
    primary = resolve_local_primary_endpoint(sidecar=False)
    if primary is not None:
        _append_endpoint(chain, primary, transport_mode=transport_mode, existing_fingerprints=build_fps)

    if settings.ai_soc_llm_planner_qwen_failover_enabled:
        qwen = resolve_qwen_primary_endpoint(sidecar=False)
        if qwen is not None:
            _append_endpoint(chain, qwen, transport_mode=transport_mode, existing_fingerprints=build_fps)

    fallback = resolve_foundation_sec_instruct_endpoint(sidecar=False)
    if fallback is not None:
        _append_endpoint(chain, fallback, transport_mode=transport_mode, existing_fingerprints=build_fps)

    if not chain:
        return None
    return FailoverChatClient(chain=tuple(chain), transport_mode=transport_mode)


def build_planner_prompts(
    query: str,
    *,
    target_index: str | None = None,
    spl_approved: bool = False,
    rbac_role: str | None = None,
) -> tuple[str, str]:
    """Calibrated, closed-set tool-planning prompt grounded in the playbook."""
    playbook = load_playbook()
    tools: dict[str, Any] = playbook["tools"]

    lines: list[str] = []
    blocked: list[str] = []
    for name, spec in tools.items():
        if spec.get("blocked"):
            blocked.append(name)
            continue
        produces = ", ".join(spec.get("produces") or []) or "none"
        preconds = ", ".join(spec.get("preconditions") or []) or "none"
        note = ""
        if name == "splunk_get_index_info":
            note = " (include only if a specific index is named)"
        elif name == "splunk_run_query":
            note = " (MUST be last; include only if spl_approved is true)"
        lines.append(f"- {name} — produces: {produces} — preconditions: {preconds}{note}")

    system = (
        "You are a deterministic SOC tool-planner. Decide which read-only Splunk "
        "MCP tools to call, and in what order, to answer the analyst query. You only "
        "plan. You never execute.\n\n"
        "TOOLS (use these exact names; nothing else exists):\n"
        + "\n".join(lines)
        + "\n\nBLOCKED (never include): "
        + ", ".join(blocked)
        + "\n\nRULES:\n"
        "1. Order strictly by data dependency: a tool may appear only after the tools that produce its preconditions.\n"
        "2. Discovery before search. splunk_run_query is always last.\n"
        "3. Include only tools whose output is needed for this query. Do not pad.\n"
        "4. Never invent tools. Never include blocked tools.\n"
        "5. splunk_run_query only returns events already indexed in Splunk. It cannot fetch "
        "vulnerability/CVE data, asset/CMDB data, or identity data not indexed in Splunk. If any "
        "part of the query needs data no listed tool produces, put it in unservable and do not "
        "claim splunk_run_query covers it.\n\n"
        "OUTPUT: a single JSON object only. No prose, no markdown.\n"
        '{"tools":["ordered names"],"reason":{"tool":"why"},"excluded":{"tool":"why omitted"},'
        '"unservable":["query part no tool can serve"]}\n\n'
        "EXAMPLE 1\n"
        'Input: {"query":"list which indexes exist","index":null,"spl_approved":false}\n'
        'Output: {"tools":["splunk_get_info","splunk_get_indexes"],"reason":{"splunk_get_info":"confirm reachable",'
        '"splunk_get_indexes":"question asks for index list"},"excluded":{"splunk_get_metadata":"no field detail",'
        '"splunk_get_index_info":"no index named","splunk_get_knowledge_objects":"no reuse needed",'
        '"splunk_run_query":"no approved SPL"},"unservable":[]}\n\n'
        "EXAMPLE 2\n"
        'Input: {"query":"show failed logins and the asset owner of each affected host","index":"auth","spl_approved":true}\n'
        'Output: {"tools":["splunk_get_info","splunk_get_indexes","splunk_get_metadata","splunk_get_index_info","splunk_run_query"],'
        '"reason":{"splunk_get_info":"confirm reachable","splunk_get_indexes":"confirm auth accessible",'
        '"splunk_get_metadata":"auth fields to build search","splunk_get_index_info":"auth index named",'
        '"splunk_run_query":"return failed-login events"},"excluded":{"splunk_get_knowledge_objects":"no reuse needed"},'
        '"unservable":["asset owner of each host (no asset/CMDB tool; not indexed in Splunk)"]}'
    )
    user = (
        "Input: "
        + json.dumps(
            {
                "query": query,
                "index": target_index,
                "spl_approved": bool(spl_approved),
                "rbac_role": rbac_role,
            }
        )
        + "\nOutput:"
    )
    return system, user


def _extract_proposed_tools(text: str) -> tuple[list[str] | None, dict[str, Any] | None]:
    """Parse the model's JSON; return (tools, full_object). Tolerant of stray prose."""
    if not text:
        return None, None
    candidate = text.strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = candidate[start : end + 1]
    try:
        obj = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None, None
    if not isinstance(obj, dict):
        return None, None
    tools = obj.get("tools")
    if not isinstance(tools, list):
        return None, obj
    return [str(t) for t in tools], obj


def plan_tool_chronology(
    query: str,
    *,
    target_index: str | None = None,
    include_knowledge_objects: bool = True,
    spl_approved: bool = False,
    rbac_role: str | None = None,
    client: FailoverChatClient | None = None,
) -> dict[str, Any]:
    """Propose via LLM, review deterministically, fall back to deterministic default.

    Returns a dict with the reviewed ``ChronologyPlan`` plus planner metadata.
    Never raises on LLM failure — deterministic default carries.
    """
    deterministic_fallback: dict[str, Any] = {
        "llm_called": False,
        "llm_label": None,
        "llm_unservable": [],
        "llm_error": None,
    }

    def _wrap(plan: ChronologyPlan, meta: dict[str, Any]) -> dict[str, Any]:
        payload = plan.to_dict()
        payload["planner"] = meta
        return payload

    active = client if client is not None else build_planner_client()
    if active is None:
        plan = review_proposed_tool_chronology(
            None,
            target_index=target_index,
            include_knowledge_objects=include_knowledge_objects,
            spl_approved=spl_approved,
            rbac_role=rbac_role,
        )
        meta = dict(deterministic_fallback)
        meta["llm_error"] = "no_planner_endpoint_configured"
        return _wrap(plan, meta)

    system, user = build_planner_prompts(
        query,
        target_index=target_index,
        spl_approved=spl_approved,
        rbac_role=rbac_role,
    )
    try:
        result = active.generate(
            system_prompt=system,
            user_prompt=user,
            max_tokens=PLANNER_MAX_TOKENS,
            temperature=PLANNER_TEMPERATURE,
            response_format=PLANNER_RESPONSE_FORMAT,
        )
    except LocalChatError as exc:
        logger.warning("tool_planner llm failed code=%s; using deterministic default", exc.code)
        plan = review_proposed_tool_chronology(
            None,
            target_index=target_index,
            include_knowledge_objects=include_knowledge_objects,
            spl_approved=spl_approved,
            rbac_role=rbac_role,
        )
        meta = dict(deterministic_fallback)
        meta["llm_error"] = exc.code
        return _wrap(plan, meta)

    proposed, obj = _extract_proposed_tools(result.text)
    unservable = []
    if isinstance(obj, dict) and isinstance(obj.get("unservable"), list):
        unservable = [str(u) for u in obj["unservable"]]

    plan = review_proposed_tool_chronology(
        proposed,
        target_index=target_index,
        include_knowledge_objects=include_knowledge_objects,
        spl_approved=spl_approved,
        rbac_role=rbac_role,
    )
    meta = {
        "llm_called": True,
        "llm_label": result.answered_label or None,
        "llm_unservable": unservable,
        "llm_error": None if proposed is not None else "llm_output_unparseable",
    }
    return _wrap(plan, meta)
