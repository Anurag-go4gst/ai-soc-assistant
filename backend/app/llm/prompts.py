"""Prompt contracts for the governed LLM layer.

These contracts are documentation/configuration only in Stage 3J-B/3J-C/3J-I.3. They
are not executed by the runtime and must not be used to bypass deterministic
routing, validation, synthesis, answer guard, or MCP execution gates.
"""

from __future__ import annotations

from typing import Any

SYSTEM_PLACEHOLDER = "AI SOC Assistant placeholder prompt. Production prompts are not implemented yet."

PROMPT_CONTRACTS: dict[str, dict[str, Any]] = {
    "intent_shadow_classifier": {
        "model_family": "Foundation-sec-8B-Instruct",
        "purpose": "Classify user query into intent, entity, use case, requested output, and skill hints.",
        "max_input_tokens": "1000-2000",
        "system_instruction": (
            "You are V.AI SOC query understanding module. Return JSON only. "
            "Do not add markdown or prose before or after JSON. Use allowed enums only. "
            "Do not invent use_case_id. Do not invent entities. If the user says "
            "`this alert`, `this incident`, `this event`, `this login`, `this user`, "
            "or similar and no context is provided, set clarification_needed=true. "
            "If clarification_needed=true, requested_output_type must be clarification. "
            "Deterministic clarification guard remains authoritative."
        ),
        "include": [
            "raw_query",
            "allowed primary_intent values",
            "allowed requested_output_type values",
            "small allowed use_case_id list",
            "allowed routable skills",
            "allowed pipeline stages",
            "allowed source types",
            "event_type normalization values",
        ],
        "exclude": [
            "Splunk rows",
            "RAG chunks",
            "MITRE long descriptions",
            "developer trace",
            "full use-case catalogue when too large",
        ],
        "output_schema": {
            "raw_query": "",
            "primary_intent": "",
            "requested_output_type": "",
            "entities": {
                "asset": None,
                "user": None,
                "source_ip": None,
                "time_window": None,
                "event_type": None,
            },
            "candidate_use_case_id": "",
            "selected_skill": "",
            "routable_skills": [],
            "pipeline_stages": [],
            "required_sources": [],
            "optional_sources": [],
            "clarification_needed": False,
            "clarification_question": None,
            "confidence": 0.0,
        },
        "consumption_rules": [
            "Parse JSON and reject unsafe prose extraction failures.",
            "Validate enum values and use_case_id against registry.",
            "Normalize event_type.",
            "Compare with deterministic classifier.",
            "Prefer deterministic result or ask clarification on mismatch.",
            "Confidence is advisory metadata only and never skips deterministic clarification.",
            "Never route tools directly from LLM shadow output.",
        ],
    },
    "pattern_reasoner": {
        "model_family": "Foundation-sec-8B-Reasoning",
        "purpose": "Produce advisory security reasoning from already provided evidence.",
        "max_input_tokens": "4000-8000",
        "system_instruction": (
            "You are Foundation-sec reasoning module inside V.AI SOC. Analyze only "
            "provided evidence. Return JSON only. The adapter may extract JSON because "
            "Foundation-sec-8B-Reasoning may emit preamble, but you must not add prose. "
            "This output is advisory only. Do not invent facts. Cannot override severity. "
            "Cannot override MITRE status. Cannot override SOP citation. Cannot add "
            "remediation. Cannot decide execution eligibility. Use generic severity fields "
            "`why_selected`, `why_not_higher`, and `escalate_if`."
        ),
        "include": [
            "StructuredContext",
            "summarized SourceEvidence",
            "relevant SPL result summary",
            "MITRE candidates",
            "severity decision",
            "missing evidence",
            "SOP guidance bullets",
            "allowed and blocked actions",
        ],
        "exclude": [
            "raw unrestricted log dumps",
            "secrets",
            "credentials",
            "draft/unapproved RAG docs",
            "full developer trace",
            "irrelevant use cases",
        ],
        "output_schema": {
            "reasoning_summary": "",
            "pattern_characterization": "",
            "mitre_reasoning": [
                {"technique_id": "", "status": "", "reasoning": "", "evidence_refs": []}
            ],
            "missing_evidence_analysis": [
                {"missing_item": "", "why_it_matters": "", "recommended_pivot": ""}
            ],
            "why_selected": [],
            "why_not_higher": [],
            "escalate_if": [],
            "investigation_pivots": [
                {"priority": "", "pivot": "", "why": "", "required_source": ""}
            ],
            "unsupported_claims_to_avoid": [],
        },
        "consumption_rules": [
            "Treat every field as advisory.",
            "Never override severity matrix or deterministic MITRE policy.",
            "Never override governed RAG SOP citation/source refs.",
            "Never add remediation.",
            "Never mark SPL or actions execution eligible.",
            "Merge only validated reasoning fields into a later synthesis package.",
            "Drop unsupported facts and record guard warning.",
        ],
    },
    "analyst_response_drafter": {
        "model_family": "Foundation-sec-8B-Instruct",
        "purpose": "Draft analyst_response JSON from approved evidence and deterministic constraints.",
        "max_input_tokens": "3000-6000",
        "system_instruction": (
            "You are V.AI SOC analyst response drafting module. Return JSON only. "
            "Use only provided evidence and constraints. Severity is fixed by the "
            "severity matrix. MITRE mapping/status is fixed by MITRE policy. SOP "
            "citation/source refs are fixed by governed RAG. Allowed/blocked actions "
            "are fixed by action policy. Priority enum must be P1/P2/P3/P4 only. "
            "Do not compute aggregate counts; use only precomputed aggregate values "
            "supplied by StructuredContext. SOP guidance must be copied from provided "
            "SOP guidance text, not converted into action IDs. Do not claim unknown "
            "facts positively or negatively. Do not mention privileged-account status, "
            "asset criticality, source ownership, post-login activity, or compromise "
            "unless evidence is supplied. Do not expose internal terms or developer trace."
        ),
        "include": [
            "fixed severity",
            "fixed finding type",
            "fixed MITRE mapping/status",
            "fixed SOP citation/source refs",
            "approved result table",
            "allowed actions",
            "blocked actions",
            "missing evidence",
            "precomputed aggregate values from StructuredContext",
            "analyst_response JSON schema",
        ],
        "exclude": [
            "raw tool trace",
            "hidden internal labels",
            "secrets",
            "action types beyond allowed tier",
        ],
        "output_schema": {
            "severity_label": "",
            "finding_title": "",
            "analyst_summary": "",
            "splunk_results_table": [],
            "mitre_mappings": [],
            "retrieved_playbook": {},
            "foundation_sec_analysis": "",
            "recommended_actions": [],
            "missing_evidence": [],
            "blocked_actions": [],
            "priority": "P3",
        },
        "consumption_rules": [
            "Parse and validate JSON schema.",
            "Answer Guard must validate before display.",
            "Semantic guard rules validate evidence presence, aggregate fidelity, SOP fidelity, MITRE status, severity authority, action tier, priority enum, internal leakage, and Splunk table fidelity before any future display path.",
            "Confidence is advisory metadata only and never approves display.",
            "Fallback to deterministic response or analyst_review_required if invalid.",
            "Never display raw LLM output directly.",
        ],
    },
    "spl_advisory_generator": {
        "model_family": "Foundation-sec-8B-Instruct or Foundation-sec-8B-Reasoning",
        "purpose": "Suggest candidate SPL only when deterministic template coverage is missing.",
        "max_input_tokens": "2000-4000",
        "system_instruction": (
            "You are V.AI SOC SPL advisory module. Return JSON only. Candidate-only. "
            "Never execution eligible. `execution_eligible` is ignored by the adapter "
            "and forced false. The production path is template-first. Use SCD field map "
            "only. Do not include alert, sendemail, write, delete, collect, outputlookup, "
            "or other write/remediation commands. Do not invent index, sourcetype, or fields. "
            "Raw candidate_spl never reaches MCP."
        ),
        "include": [
            "use_case_id",
            "SCD field map",
            "allowed indexes",
            "allowed sourcetypes",
            "required fields",
            "allowed commands",
            "template hints",
        ],
        "output_schema": {
            "candidate_spl": "",
            "assumptions": [],
            "required_fields": [],
            "validation_notes": [],
            "execution_eligible": False,
        },
        "consumption_rules": [
            "Prefer deterministic SPL templates before any advisory generation.",
            "Pass to deterministic SPL validator.",
            "Mark not recommended if validation fails.",
            "Adapter forces execution_eligible=false for all LLM SPL.",
            "Never execute raw candidate_spl.",
            "Only normalized_spl can enter MCP gate.",
        ],
    },
}

for _reasoning_role in ("mitre_reasoner", "missing_evidence_reasoner", "risk_rationale_reasoner"):
    PROMPT_CONTRACTS[_reasoning_role] = {
        **PROMPT_CONTRACTS["pattern_reasoner"],
        "purpose": f"Produce advisory {_reasoning_role.replace('_', ' ')} output from already provided evidence.",
    }

PROMPT_CONTRACTS["investigation_note_drafter"] = {
    **PROMPT_CONTRACTS["analyst_response_drafter"],
    "purpose": "Draft investigation note content from approved evidence and deterministic constraints.",
}

PROMPT_CONTRACTS["answer_guard_assistant"] = {
    "model_family": "Foundation-sec-8B-Reasoning",
    "purpose": "Planned advisory assistance for future Answer Guard design; dormant and not executed in this stage.",
    "max_input_tokens": "4000-8000",
    "system_instruction": (
        "Return JSON only. Advisory only. Deterministic Answer Guard remains authoritative. "
        "Do not approve final answers, do not block live responses, do not call tools, and do not decide execution eligibility."
    ),
    "include": [
        "planned guard findings",
        "deterministic policy decisions",
        "validated source refs",
    ],
    "exclude": [
        "raw LLM output display",
        "secrets",
        "tool credentials",
        "MCP execution payloads",
    ],
    "output_schema": {
        "guard_assist": "",
        "advisory_findings": [],
        "confidence": 0.0,
    },
    "consumption_rules": [
        "Not called in Stage 3J-I.3.",
        "Must not override deterministic Answer Guard.",
        "Confidence is advisory metadata only.",
    ],
}
