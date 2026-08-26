"""P8 candidate prompt overlays. Production ACTIVE contracts are not edited here.

Live hops read ``live_system_prompt(role, active_text)``. The candidate text is
used only when ``prompt_eval_arm() == 'candidate'``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256

from app.llm.policy.eval_arm import prompt_eval_arm

CANDIDATE_STATUS = "CANDIDATE"


@dataclass(frozen=True)
class CandidatePrompt:
    role_id: str
    template_id: str
    version: str
    status: str
    system_instruction: str
    extra_few_shots: tuple[dict[str, object], ...] = ()


_T4_CANDIDATE_INSTRUCTION = (
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
    "optional and non-authoritative. One JSON object, no markdown, no prose.\n"
    "LOCKED FIELDS ARE IMMUTABLE: never change values already present in derived hints "
    "or EXPLICIT_USER_LITERAL_CONSTRAINTS. If a host/user/IP is already supplied, omit "
    "entities entirely rather than restating or mutating it.\n"
    "FILL MISSING FIELDS ONLY. Do not rewrite a complete deterministic goal.\n"
    "DO NOT INVENT ENTITIES. Leave entities as {}. Do not emit host, server, user, "
    "machine, endpoint, target, source, or destination unless that exact token appears "
    "in the query as a specific hostname, IP, or username.\n"
    "DO NOT INVENT TIME. If the query has no time window, omit time_scope.\n"
    "A category such as 'suspicious DNS' or 'the estate' is not an entity.\n"
    "If derived hints already contain entities.host, omit the entities key. "
    "Do not restate or replace a locked host.\n"
    "Always emit competing_hypotheses (two short labels) and evidence_requirements "
    "(two evidence categories). Omit the entities and time_scope keys entirely — "
    "do not send null, empty objects, or generic nouns."
)

_T4_EXTRA_SHOTS: tuple[dict[str, object], ...] = (
    {
        "label": "NEG invented host",
        "query": "powershell on endpoints talking to new domains",
        "output": {
            "normalized_goal": "find powershell process activity contacting previously unseen domains",
            "clarification_required": False,
            "competing_hypotheses": ["admin software", "malicious staging"],
            "evidence_requirements": ["endpoint process telemetry", "dns or proxy logs"],
        },
    },
    {
        "label": "NEG invented time",
        "query": "signs that something is moving sideways through the estate",
        "output": {
            "normalized_goal": "identify signs of lateral movement across the estate",
            "clarification_required": False,
            "competing_hypotheses": ["admin tooling", "unauthorized movement"],
            "evidence_requirements": ["internal auth hops", "process execution"],
        },
    },
    {
        "label": "NEG locked host mutation",
        "query": "is this brute force or a locked account",
        "note": "derived hints already have entities.host; omit entities",
        "output": {
            "normalized_goal": "determine whether failed logons are brute force or a locked account",
            "clarification_required": False,
            "competing_hypotheses": ["brute force", "account lockout"],
            "evidence_requirements": ["failed logon counts", "lockout events"],
        },
    },
    {
        "label": "POS missing-only completion",
        "query": "dns queries that look algorithmically generated",
        "output": {
            "normalized_goal": "find dns queries that look algorithmically generated",
            "clarification_required": False,
            "competing_hypotheses": ["dga malware", "software update noise"],
            "evidence_requirements": ["dns query logs", "nxdomain rates"],
        },
    },
    {
        "label": "POS clarify unresolved referent",
        "query": "compare this with what happened last week and tell me if it is getting worse",
        "output": {
            "semantic_ambiguity": "clarification_required",
            "clarification_required": True,
            "clarification_reason": "which event 'this' refers to",
        },
    },
)

_SPL_CANDIDATE_INSTRUCTION = (
    "You are an OT/SOC detection PLANNER. Given an investigation request, return a small JSON "
    "detection plan — NOT SPL. Deterministic code compiles your plan into a validated, review-only "
    "query, so do not write any SPL or pipes.\n"
    "Return only valid JSON. No markdown, no explanation outside JSON, no hidden reasoning, no "
    "scratchpad, no planning text, and no <think> tags.\n"
    "Describe: data_domain (one of auth, network, dns, endpoint, firewall, ot_protocol, ot_network); "
    "filters as field+match pairs using generic field names (src_ip, dest_ip, user, host, protocol, "
    "function_code, query, action, bytes_out); group_by entities; metric (count or distinct_count, "
    "with metric_field for distinct_count); source fields index and sourcetype; time fields earliest/latest "
    "or time_window_hours; result_cap; unresolved_slots; a short detection_family; assumptions and required_fields. "
    "Pick the data_domain that matches the question. Keep filters minimal and on-question.\n"
    "Preserve the semantic contract exactly.\n"
    "ROLLING: keep the grouping entity, distinct vs non-distinct metric, window width, horizon, and "
    "the filtered event population.\n"
    "TREND: keep time horizon, bucket grain, metric, filters, and grouping.\n"
    "SEQUENCE: keep event A, event B, order, same-entity correlation, max gap, horizon, and filters.\n"
    "RANKING: keep the filter population (including denied/blocked/action filters), aggregation, "
    "ranking entity, and sort direction. Add a numeric limit only when the request asked for one.\n"
    "RAW: keep the event population and time bound; do not aggregate away the raw events.\n"
    "Never drop a denied_traffic / action=denied filter. For denied firewall ranking always include "
    "{\"field\":\"action\",\"match\":\"denied\"}. Never invent `| head 100` in the plan. "
    "Never emit a filter whose match is 'is not null', 'not null', '*', or 'any'. "
    "If the request names no concrete IOC, use filters []. The compiler supplies rolling/trend/"
    "sequence windows. The compiled candidate is review-only and never execution eligible."
)

_PLANNER_CANDIDATE_INSTRUCTION = (
    "You are the advisory investigation planning role. Return JSON only. "
    "No markdown. No wrapper key named investigation_plan. "
    "Start with hypotheses and evidence_needed as arrays (use [] if empty). "
    "Also include data_categories, rag_sufficient, env_kb_needed, discovery_needed, "
    "read_only_tools, safe_spl_templates, spl_review_requested, clarification_needed, "
    "clarification_questions, refinement_recommended. Keep arrays short. "
    "capability_requests must be []. Never emit entities, SPL, or execution flags. "
    "Review-only: do not authorize writes or containment."
)

CANDIDATES: dict[str, CandidatePrompt] = {
    "semantic_t4": CandidatePrompt(
        role_id="semantic_t4",
        template_id="tmpl.semantic_t4.candidate",
        version="1.2.0-candidate",
        status=CANDIDATE_STATUS,
        system_instruction=_T4_CANDIDATE_INSTRUCTION,
        extra_few_shots=_T4_EXTRA_SHOTS,
    ),
    "spl_advisory_generator": CandidatePrompt(
        role_id="spl_advisory_generator",
        template_id="tmpl.spl_advisory_generator.candidate",
        version="1.2.0-candidate",
        status=CANDIDATE_STATUS,
        system_instruction=_SPL_CANDIDATE_INSTRUCTION,
    ),
    "investigation_planner": CandidatePrompt(
        role_id="investigation_planner",
        template_id="tmpl.investigation_planner.candidate",
        version="1.2.0-candidate",
        status=CANDIDATE_STATUS,
        system_instruction=_PLANNER_CANDIDATE_INSTRUCTION,
    ),
}


def candidate_for(role_id: str) -> CandidatePrompt | None:
    return CANDIDATES.get(role_id)


def candidate_stable_prefix_hash(role_id: str) -> str:
    from app.llm.policy.registry import contract_for
    from app.llm.policy.templates import build_stable_prefix

    cand = CANDIDATES[role_id]
    overlay = replace(
        contract_for(role_id),
        system_instruction=cand.system_instruction,
        prompt_template_id=cand.template_id,
        prompt_version=cand.version,
    )
    return sha256(build_stable_prefix(overlay).encode("utf-8")).hexdigest()


def live_system_prompt(role_id: str, active_prompt: str) -> str:
    """Production default is the supplied ACTIVE live prompt. Candidate only under eval arm."""
    from app.llm.policy.request_provenance import record_selected_system_prompt

    if prompt_eval_arm() != "candidate":
        record_selected_system_prompt(
            role_id=role_id,
            template_id="",
            version="",
            status="ACTIVE",
            system_instruction=active_prompt,
        )
        return active_prompt
    cand = candidate_for(role_id)
    if cand is None:
        record_selected_system_prompt(
            role_id=role_id,
            template_id="",
            version="",
            status="ACTIVE",
            system_instruction=active_prompt,
        )
        return active_prompt
    record_selected_system_prompt(
        role_id=role_id,
        template_id=cand.template_id,
        version=cand.version,
        status=cand.status,
        system_instruction=cand.system_instruction,
        prefix_hash=candidate_stable_prefix_hash(role_id),
    )
    return cand.system_instruction


def extra_few_shots_for_live(role_id: str) -> tuple[dict[str, object], ...]:
    if prompt_eval_arm() != "candidate":
        return ()
    cand = candidate_for(role_id)
    if cand is None:
        return ()
    return cand.extra_few_shots
