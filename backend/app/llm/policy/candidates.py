"""P8 candidate prompt overlays. Production ACTIVE contracts are not edited here.

Live hops read ``live_system_prompt(role, active_text)``. The candidate text is
used only when ``prompt_eval_arm() == 'candidate'``.
"""

from __future__ import annotations

import json
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


#: T4 candidate v2 — deliberately short.
#:
#: v1 was a fifteen-rule wall plus five extra examples, and measured worse than
#: no prompt at all: on all four frozen T4 rows the model returned EMPTY
#: competing_hypotheses and EMPTY evidence_requirements (the two things every T4
#: row is actually scored on), and on two unrelated rows it emitted a goal
#: containing "compare ... with last week", copied out of a neighbouring example.
#:
#: v2 stated the required output first, kept three prohibitions, and added no
#: examples of its own. It took T4 accept 0/4 -> 4/4, but left one defect:
#: v2 said "give clarification_reason and stop", which contradicts the required
#: arrays -- the model cannot stop and also fill them. Measured, the model
#: resolved the contradiction by not clarifying at all, so L3.T4.03 kept failing
#: even though the same model clarifies that request correctly when the arrays
#: are optional.
#:
#: v3 removes the contradiction rather than the requirement: clarifying and
#: filling the arrays are stated as compatible, because naming the evidence that
#: WOULD settle a question is not a claim to have understood which question was
#: asked. One synthetic example, deliberately not from the frozen bank.
_T4_CANDIDATE_INSTRUCTION = (
    "T1-T3 abstained. Propose the meaning of the whole SOC request. "
    "Return one JSON object, no markdown, no prose.\n"
    "ALWAYS include both of these, and never leave either empty — in every answer, "
    "including a clarification:\n"
    "  competing_hypotheses: exactly two short labels, one benign and one malicious, "
    "as possibilities — never a conclusion.\n"
    "  evidence_requirements: exactly two categories of evidence that would settle it "
    "(for example 'authentication logs', 'dns query logs') — categories, never findings.\n"
    "CLARIFICATION. Set clarification_required true when the request points at something "
    "you were not given: 'this', 'that alert', 'the same as before', an earlier incident, "
    "campaign or turn that is not in the request. Give clarification_reason naming exactly "
    "what is unidentified. Do not invent the missing thing.\n"
    "Filling the two arrays above is NOT a claim that you understood the request. Naming the "
    "evidence that WOULD settle a question is always possible; identifying WHICH question was "
    "asked is not. So a clarification answer still carries both arrays, fully populated, "
    "alongside clarification_required true. Never drop clarification just to fill them, and "
    "never invent an identity just to fill them.\n"
    "Missing logs, evidence, thresholds or detection criteria are NOT a reason to clarify: a "
    "broad hunt has a clear meaning, so resolve it normally.\n"
    "Restate the request as normalized_goal in your own words. Describe ONLY what this "
    "request asks. Never carry over wording, a time period, or a comparison from any "
    "example — an example shows the shape, not the content.\n"
    "Do not invent an entity. Omit the entities key. A hostname, username or IP belongs "
    "there only if that exact token is in the request; a category such as 'the estate' or "
    "'suspicious DNS' is a topic, not an entity.\n"
    "Do not invent a time window. If the request states no time period, omit time_scope.\n"
    "Never change a value already supplied in EXPLICIT_USER_LITERAL_CONSTRAINTS or in the "
    "derived hints; those are locked.\n"
    "Grant no route, capability, SPL, MCP, RBAC, HIL or action authority."
)

#: One synthetic shot for the clarification-with-arrays shape.
#:
#: Deliberately NOT a frozen-bank question, and not a paraphrase of one:
#: test_p8_prompt_candidates.py pins that no shape example matches a bank row.
#: v1's shots were near-verbatim bank questions and bled across examples, which
#: is why v2 shipped none at all; this one exists only because the measured
#: v2 defect is specifically that the model never demonstrates the combination.
_T4_EXTRA_SHOTS: tuple[dict[str, object], ...] = (
    {
        "label": "CLARIFY (unidentified referent) — note both arrays stay populated",
        "query": "is the current activity the same intrusion campaign we tracked before",
        "output": {
            "normalized_goal": "compare current activity against a previously tracked intrusion campaign",
            "semantic_ambiguity": "clarification_required",
            "clarification_required": True,
            "clarification_reason": "neither the current activity nor the earlier campaign is identified in the request",
            "competing_hypotheses": ["unrelated activity", "same actor resuming"],
            "evidence_requirements": ["prior campaign case record", "current detection telemetry"],
        },
    },
)

_SPL_CANDIDATE_INSTRUCTION = (
    "You are a Splunk SOC detection PLANNER. The SIEM is Splunk and the query language is SPL, "
    "but you do not write SPL. Return a small JSON detection plan; deterministic code compiles it "
    "into a validated, review-only SPL candidate. Write no SPL, no pipes, no commands.\n"
    "Return one JSON object. No markdown, no prose outside JSON, no scratchpad, no <think> tags.\n"
    "Fields: detection_family (short label); data_domain (auth, network, dns, endpoint, firewall, "
    "ot_protocol, ot_network); filters; group_by; metric (count or distinct_count) with metric_field "
    "for distinct_count; required_fields. Pick the data_domain the question is actually about.\n"
    "FILTERS ARE EVENT-SELECTION PREDICATES ONLY — a field and the literal value that selects the "
    "events to search. Every filter must be a real predicate that Splunk can match.\n"
    "Never emit a filter whose match is 'not null', 'is not null', 'distinct', '*', 'any', or the "
    "name of an operation. Those are not values. If the request names no concrete literal to match "
    "on, return filters [].\n"
    "THE COMPILER OWNS ANALYSIS MECHANICS. Never encode a rolling window, a time bucket or span, a "
    "sort order, an event ordering, a time horizon, or a result cap as a filter or as any other "
    "field. Never invent a threshold.\n"
    "For an ordered A-then-B sequence, do NOT put the two event types in filters: they are "
    "alternatives, not conditions that hold together, and ANDing them selects nothing. Leave filters "
    "[] and name the correlation entity in group_by.\n"
    "Keep the mandatory population filter the request states — a denied/blocked firewall question "
    "always keeps {\"field\": \"action\", \"match\": \"denied\"} (or \"blocked\").\n"
    "Do not invent an index or sourcetype; the governed source mapping supplies them.\n"
    "The compiled candidate is review-only and is never execution eligible."
)

#: Candidate few-shot CONTENT keyed to the deterministic analysis shape.
#:
#: ``few_shot_catalog_v1`` already declares one shape-keyed asset per SPL shape
#: (``fs.spl.rolling`` and siblings), but the catalogue carries metadata only —
#: no runtime ever rendered an exemplar. Exactly one of these is appended to the
#: user prompt, chosen by the shape the deterministic semantic contract already
#: resolved, so no second classifier is introduced and the cacheable system
#: prefix is unchanged.
#:
#: Each example is keyed to a reusable shape, never to a bank question.
_SPL_SHAPE_FEW_SHOTS: dict[str, dict[str, object]] = {
    "rolling": {
        "example_id": "fs.spl.rolling.plan.candidate",
        "request": "a single source IP hitting many different user accounts within a rolling 15 minute window",
        "plan": {
            "detection_family": "credential_spray_rolling",
            "data_domain": "auth",
            "filters": [{"field": "action", "match": "failure"}],
            "group_by": ["src_ip"],
            "metric": "distinct_count",
            "metric_field": "user",
            "required_fields": ["src_ip", "user", "action"],
        },
        "note": "The rolling window itself is not in the plan; the compiler applies it.",
    },
    "trend": {
        "example_id": "fs.spl.trend.plan.candidate",
        "request": "successful VPN logins per 30 minutes over the last 6 hours",
        "plan": {
            "detection_family": "auth_success_trend",
            "data_domain": "auth",
            "filters": [{"field": "action", "match": "success"}],
            "group_by": [],
            "metric": "count",
            "required_fields": ["action"],
        },
        # `_time` is deliberately absent from required_fields: listing it led the
        # model to put _time in group_by, which buckets a timechart by itself.
        "note": (
            "No bucket, span or horizon in the plan; the compiler owns the time grain. "
            "Never put _time in group_by — the time axis is not a grouping entity."
        ),
    },
    "sequence": {
        "example_id": "fs.spl.sequence.plan.candidate",
        # Phrased generically on purpose. A concrete pair of event names here was
        # copied verbatim into the answer for an unrelated sequence question.
        "request": "one kind of event followed by a different kind of event for the same account, within a few minutes",
        "plan": {
            "detection_family": "ordered_event_sequence",
            "data_domain": "auth",
            "filters": [],
            "group_by": ["user"],
            "metric": "count",
            "required_fields": ["user", "event_type"],
        },
        "note": (
            "filters MUST stay empty for a sequence. The two event kinds are alternatives, not "
            "conditions that hold at once, so naming them as filters selects nothing. Name only "
            "the entity the two events must share, in group_by. Use the event names from the "
            "request being answered, never from this example."
        ),
    },
    "ranking": {
        "example_id": "fs.spl.ranking.plan.candidate",
        "request": "which destination ports saw the most blocked connections",
        "plan": {
            "detection_family": "blocked_dest_port_ranking",
            "data_domain": "firewall",
            "filters": [{"field": "action", "match": "blocked"}],
            "group_by": ["dest_port"],
            "metric": "count",
            "required_fields": ["dest_port", "action"],
        },
        "note": "The blocked/denied population filter is mandatory. No cap unless one was asked for.",
    },
    "raw": {
        "example_id": "fs.spl.raw_events.plan.candidate",
        "request": "show me the raw VPN authentication failures for user bob",
        "plan": {
            "detection_family": "raw_auth_events",
            "data_domain": "auth",
            "filters": [
                {"field": "user", "match": "bob"},
                {"field": "action", "match": "failure"},
            ],
            "group_by": ["src_ip"],
            "metric": "count",
            "required_fields": ["user", "src_ip", "action"],
        },
        "note": (
            "Named literals from the request become filters verbatim. Never put _time in "
            "group_by — the time axis is not a grouping entity."
        ),
    },
}


def spl_shape_few_shot_block(analysis_shape: str) -> str:
    """Render the one shape-keyed plan example, or '' outside the candidate arm.

    The shape comes from the deterministic semantic contract
    (``build_spl_intent_spec``), so selection reuses existing authority. An
    unknown or unsupported shape renders nothing rather than a wrong example.
    """
    if prompt_eval_arm() != "candidate":
        return ""
    shot = _SPL_SHAPE_FEW_SHOTS.get(str(analysis_shape or "").strip().lower())
    if not shot:
        return ""
    plan_json = json.dumps(shot["plan"], separators=(",", ":"), sort_keys=True)
    # The rule precedes the JSON: a rule placed after the example is read as a
    # footnote, and the example gets copied instead of applied.
    return (
        "Worked example of a plan for this SHAPE of request "
        f"({shot['example_id']}). Copy its STRUCTURE only — every value below must "
        "come from the actual request above, never from this example.\n"
        f"Rule for this shape: {shot['note']}\n"
        f"Example request: {shot['request']}\n"
        f"Example plan: {plan_json}"
    )

#: The two observed planner failures are both format failures, not reasoning
#: failures: the ACTIVE arm wrapped the payload in an ``investigation_plan`` key
#: (rejected by ``additionalProperties: false``), and the first candidate ran past
#: the 700-token ceiling mid-object (``dropped:truncated``). One compact
#: exact-schema exemplar addresses both — it shows the twelve required keys at the
#: top level and, just as importantly, shows how terse the values must be.
_PLANNER_EXAMPLE = json.dumps(
    {
        "hypotheses": [
            "authorized user activity",
            "credential compromise",
        ],
        "evidence_needed": [
            "authentication events for the account",
            "source address history",
        ],
        "data_categories": ["authentication", "endpoint"],
        "rag_sufficient": False,
        "env_kb_needed": True,
        "discovery_needed": True,
        "read_only_tools": [],
        "safe_spl_templates": [],
        "spl_review_requested": True,
        "clarification_needed": False,
        "clarification_questions": [],
        "refinement_recommended": True,
    },
    separators=(",", ":"),
    sort_keys=True,
)

_PLANNER_CANDIDATE_INSTRUCTION = (
    "You are the advisory investigation planning role. Return exactly one JSON object.\n"
    "No markdown, no prose before or after the JSON, no <think> tags.\n"
    "Emit the twelve required keys at the TOP LEVEL of that object. Never nest them under a "
    "wrapper key such as investigation_plan, plan, or result — a wrapper is rejected.\n"
    "Keep every value short: at most two or three brief strings per array. The response is "
    "length-capped, and an object that does not close is discarded entirely.\n"
    "Planned evidence is NOT obtained evidence. Do not state that any tool ran, that any data was "
    "retrieved, or that anything was confirmed malicious. Do not claim remediation occurred.\n"
    "capability_requests must be []. Never emit entities, hostnames, usernames, addresses, time "
    "scopes, source names, tool names, SPL, severity, or execution flags.\n"
    "Review-only: propose nothing that authorizes a write, a containment or an execution.\n"
    "Exactly this shape:\n" + _PLANNER_EXAMPLE
)

#: Fields the T4 candidate arm makes mandatory in constrained decoding.
#:
#: The ACTIVE guided-decoding schema lists every property and marks none of them
#: required, so a compliant response may omit all of them — and measurably does:
#: on all four frozen T4 rows the model returned neither competing_hypotheses nor
#: evidence_requirements, which are exactly what those rows are scored on, while
#: still emitting the two keys the prompt told it to omit.
#:
#: This does not change the frozen ``SemanticT4Proposal`` contract, the merge, or
#: any deterministic authority. It asks the model for MORE, not less: the fields
#: the contract already declares are made non-optional, and the legacy aliases
#: (``ambiguity_state``, ``confidence``) are withheld so the model cannot answer
#: in the deprecated spelling instead of the frozen one.
_T4_CANDIDATE_REQUIRED_FIELDS: tuple[str, ...] = (
    "normalized_goal",
    "competing_hypotheses",
    "evidence_requirements",
    "semantic_ambiguity",
    "clarification_required",
)

_T4_CANDIDATE_WITHHELD_ALIASES: frozenset[str] = frozenset({"ambiguity_state", "confidence"})


#: Order the candidate schema puts the clarification decision in.
#:
#: Guided decoding emits properties in schema order, and generation is
#: autoregressive: with the ACTIVE order the model writes ``normalized_goal``
#: FIRST -- committing to a confident reading of the request -- and only then
#: answers ``clarification_required``, where "false" is the self-consistent
#: continuation of the goal it just wrote. Deciding first, then describing,
#: matches the order the contract actually reasons in.
#:
#: This reorders keys only. No field is added, removed, relaxed or renamed, and
#: the frozen ``SemanticT4Proposal`` is untouched -- JSON object key order is not
#: semantic to any consumer.
_T4_CANDIDATE_FIELD_ORDER: tuple[str, ...] = (
    "clarification_required",
    "clarification_reason",
    "semantic_ambiguity",
    "normalized_goal",
    "competing_hypotheses",
    "evidence_requirements",
    "semantic_confidence",
    "entities",
    "time_scope",
)


def candidate_t4_response_schema(active_schema: dict[str, object]) -> dict[str, object]:
    """Return the ACTIVE schema unchanged outside the candidate eval arm."""
    promoted = PROMOTED_TO_ACTIVE.get("semantic_t4")
    use_candidate_schema = bool(promoted and promoted.use_candidate_t4_schema)
    if prompt_eval_arm() != "candidate" and not use_candidate_schema:
        return active_schema
    source = {
        key: value
        for key, value in dict(active_schema.get("properties") or {}).items()
        if key not in _T4_CANDIDATE_WITHHELD_ALIASES
    }
    ordered = [k for k in _T4_CANDIDATE_FIELD_ORDER if k in source]
    ordered += [k for k in source if k not in ordered]
    properties = {key: source[key] for key in ordered}
    required = [name for name in _T4_CANDIDATE_REQUIRED_FIELDS if name in properties]
    return {"type": "object", "properties": properties, "required": required}


CANDIDATES: dict[str, CandidatePrompt] = {
    "semantic_t4": CandidatePrompt(
        role_id="semantic_t4",
        template_id="tmpl.semantic_t4.candidate",
        version="1.4.0-candidate",
        status=CANDIDATE_STATUS,
        system_instruction=_T4_CANDIDATE_INSTRUCTION,
        extra_few_shots=_T4_EXTRA_SHOTS,
    ),
    "spl_advisory_generator": CandidatePrompt(
        role_id="spl_advisory_generator",
        template_id="tmpl.spl_advisory_generator.candidate",
        version="1.3.0-candidate",
        status=CANDIDATE_STATUS,
        system_instruction=_SPL_CANDIDATE_INSTRUCTION,
    ),
    "investigation_planner": CandidatePrompt(
        role_id="investigation_planner",
        template_id="tmpl.investigation_planner.candidate",
        version="1.3.0-candidate",
        status=CANDIDATE_STATUS,
        system_instruction=_PLANNER_CANDIDATE_INSTRUCTION,
    ),
}


@dataclass(frozen=True)
class PromotedPrompt:
    """A candidate an operator has promoted to ACTIVE.

    Promotion is a POINTER, never an edit. ``system_instruction`` is the same
    immutable string the A/B measured -- ``PROMOTIONS`` asserts that below by
    hash -- so the text that was evaluated is exactly the text that now serves.
    The candidate entry in ``CANDIDATES`` is left untouched as historical
    evidence. Rollback is deleting the role's entry from ``PROMOTED_TO_ACTIVE``.
    """

    role_id: str
    #: ACTIVE identity after promotion: the ACTIVE template id, next version.
    template_id: str
    version: str
    #: What this rolls back to. Recorded because activation without a rollback
    #: target is refused by ``studio_config.record_activation``.
    rollback_template_id: str
    rollback_version: str
    #: The candidate this came from, for provenance.
    promoted_from_template_id: str
    promoted_from_version: str
    #: Evidence that authorised the promotion.
    evidence_ref: str
    #: semantic_t4-only: keep candidate guided-decoding order/required fields.
    use_candidate_t4_schema: bool = False
    #: semantic_t4-only: keep candidate extra shots after promotion.
    use_candidate_few_shots: bool = False


#: Roles whose evaluated candidate now serves as ACTIVE.
#:
#: investigation_planner: on the frozen 16-row bank at bank_hash 5f78ccbe…,
#: ACTIVE produced an `investigation_plan` wrapper key that
#: `additionalProperties: false` rejects, plus missing required hypotheses and
#: evidence_needed -> planner schema 0/1. The candidate produced a
#: contract-valid proposal -> 1/1, `plan_source=llm_proposed_validated`, zero
#: authority violations, zero evidence claims. Reconfirmed live before
#: promotion. See docs/evals/p8_l3/ab_v131_candidate_scorecard.json.
PROMOTED_TO_ACTIVE: dict[str, PromotedPrompt] = {
    "semantic_t4": PromotedPrompt(
        role_id="semantic_t4",
        template_id="tmpl.semantic_t4",
        version="1.1.0",
        rollback_template_id="tmpl.semantic_t4",
        rollback_version="1.0.0",
        promoted_from_template_id="tmpl.semantic_t4.candidate",
        promoted_from_version="1.4.0-candidate",
        evidence_ref="docs/evals/p8_l3/ab_v141_candidate_scorecard.json",
        use_candidate_t4_schema=True,
        use_candidate_few_shots=True,
    ),
    "investigation_planner": PromotedPrompt(
        role_id="investigation_planner",
        template_id="tmpl.investigation_planner",
        version="1.1.0",
        rollback_template_id="tmpl.investigation_planner",
        rollback_version="1.0.0",
        promoted_from_template_id="tmpl.investigation_planner.candidate",
        promoted_from_version="1.3.0-candidate",
        evidence_ref="docs/evals/p8_l3/ab_v131_comparison.json",
    ),
}


def promoted_for(role_id: str) -> PromotedPrompt | None:
    return PROMOTED_TO_ACTIVE.get(role_id)


def promoted_system_instruction(role_id: str) -> str | None:
    """The promoted text, sourced from the immutable candidate it was promoted from."""
    promoted = PROMOTED_TO_ACTIVE.get(role_id)
    if promoted is None:
        return None
    return CANDIDATES[role_id].system_instruction


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


def promoted_stable_prefix_hash(role_id: str) -> str:
    """Stable prefix under the promoted ACTIVE identity (new template id/version)."""
    from app.llm.policy.registry import contract_for
    from app.llm.policy.templates import build_stable_prefix

    promoted = PROMOTED_TO_ACTIVE[role_id]
    overlay = replace(
        contract_for(role_id),
        system_instruction=promoted_system_instruction(role_id) or "",
        prompt_template_id=promoted.template_id,
        prompt_version=promoted.version,
    )
    return sha256(build_stable_prefix(overlay).encode("utf-8")).hexdigest()


def live_system_prompt(role_id: str, active_prompt: str) -> str:
    """Production default is the supplied ACTIVE live prompt. Candidate only under eval arm.

    A promoted role serves its promoted text in BOTH arms: once a candidate is
    ACTIVE there is no longer a second arm for it, and reporting one would
    fabricate a delta against a prompt no longer in service.
    """
    from app.llm.policy.request_provenance import record_selected_system_prompt

    promoted = PROMOTED_TO_ACTIVE.get(role_id)
    if promoted is not None:
        text = promoted_system_instruction(role_id) or active_prompt
        record_selected_system_prompt(
            role_id=role_id,
            template_id=promoted.template_id,
            version=promoted.version,
            status="ACTIVE",
            system_instruction=text,
            prefix_hash=promoted_stable_prefix_hash(role_id),
        )
        return text

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
    promoted = PROMOTED_TO_ACTIVE.get(role_id)
    if role_id == "semantic_t4" and promoted and promoted.use_candidate_few_shots:
        cand = candidate_for(role_id)
        if cand is None:
            return ()
        return cand.extra_few_shots
    if prompt_eval_arm() != "candidate":
        return ()
    cand = candidate_for(role_id)
    if cand is None:
        return ()
    return cand.extra_few_shots
