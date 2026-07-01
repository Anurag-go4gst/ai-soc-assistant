"""Prompt contracts for the governed LLM layer.

These contracts are documentation/configuration only in Stage 3J-B/3J-C/3J-I.3. They
are not executed by the runtime and must not be used to bypass deterministic
routing, validation, synthesis, answer guard, or MCP execution gates.
"""

from __future__ import annotations

from typing import Any

SYSTEM_PLACEHOLDER = "AI SOC Assistant placeholder prompt. Production prompts are not implemented yet."

AUTHORITY_HIERARCHY_RULES = [
    "User-explicit values win over LLM inference.",
    "Deterministic extraction and route-plan values win over LLM inference.",
    "Environment KB/source-profile values win over LLM inference.",
    "Catalogue/manual bindings win over LLM inference.",
    "LLM output fills blanks only and must not override higher-authority bindings.",
    "When values conflict, report ambiguity or missing evidence instead of guessing.",
]

REVIEW_ONLY_SAFETY_RULES = [
    "Review-only posture: never authorize execution, containment, writes, or destructive actions.",
    "Do not claim live results, row counts, compromise, severity, or MITRE support unless provided by governed evidence.",
    "Do not execute SPL or imply candidate SPL is approved or execution eligible.",
    "Return uncertainty, missing evidence, or clarification when facts are unavailable.",
]

SOC_FEW_SHOT_COVERAGE = [
    "Windows failed logins: map failed-logon/count-by-user paraphrases to authentication evidence; do not invent index/sourcetype.",
    "Off-shift logon: preserve explicit Event 4624 and after-hours window such as 22:00-06:00; do not convert dates into hostnames.",
    "Cisco ASA IOC lookup: use firewall/network evidence hints and IOC/lookup slots only when supplied; do not pivot to asset inventory.",
    "SCADA threshold anomaly: preserve industrial/OT threshold/function-code wording; do not recast as auth logs.",
    "SMB top talkers: map to network traffic aggregation by host/src/dest as asked; do not assert lateral movement without evidence.",
    "Generic SPL request: produce review-only candidate guidance with placeholders when source profile is unknown.",
    "Conceptual knowledge question: answer as knowledge recall; do not generate SPL or live investigation claims.",
    "Unsafe containment request: classify as review/HIL guidance only; never authorize block/isolate/disable/contain actions.",
    "Ambiguous investigation: ask for the missing alert/entity/time/source detail instead of fabricating it.",
]

_AUTHORITY_PROMPT = " Authority hierarchy: " + " ".join(AUTHORITY_HIERARCHY_RULES)
_REVIEW_ONLY_PROMPT = " Review-only safety: " + " ".join(REVIEW_ONLY_SAFETY_RULES)

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
            f"{_AUTHORITY_PROMPT}"
            f"{_REVIEW_ONLY_PROMPT}"
        ),
        "authority_hierarchy": AUTHORITY_HIERARCHY_RULES,
        "review_only_safety": REVIEW_ONLY_SAFETY_RULES,
        "few_shot_coverage": SOC_FEW_SHOT_COVERAGE,
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
            f"{_REVIEW_ONLY_PROMPT}"
        ),
        "authority_hierarchy": AUTHORITY_HIERARCHY_RULES,
        "review_only_safety": REVIEW_ONLY_SAFETY_RULES,
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
            f"{_AUTHORITY_PROMPT}"
            f"{_REVIEW_ONLY_PROMPT}"
        ),
        "authority_hierarchy": AUTHORITY_HIERARCHY_RULES,
        "review_only_safety": REVIEW_ONLY_SAFETY_RULES,
        "few_shot_coverage": [
            item for item in SOC_FEW_SHOT_COVERAGE if item.startswith(("Generic SPL", "Windows", "Cisco", "SCADA", "SMB"))
        ],
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
    "template_render_parameter_assist": {
        "model_family": "Foundation-sec-8B-Instruct only",
        "purpose": "Extract render parameters for matched CIM templates; renderer is authoritative.",
        "max_input_tokens": "2000",
        "system_instruction": (
            "Return JSON only. Extract host/user/src_ip/dest_ip/result_limit/time_window values. "
            "Never emit SPL, template_id, datamodel, detection_ref, or lookup_name. "
            "Fill blanks only; route-plan parameters, user-explicit values, Environment KB/source-profile, "
            "and catalogue/manual bindings are higher authority. On conflict, keep the higher-authority "
            "value and let the adapter record the disagreement."
        ),
        "authority_hierarchy": AUTHORITY_HIERARCHY_RULES,
        "review_only_safety": REVIEW_ONLY_SAFETY_RULES,
        "include": ["user_query", "matched_template_id", "route_plan_time_window"],
        "output_schema": {
            "extracted_parameters": {
                "host": "app-01",
                "src_ip": "10.0.0.5",
                "result_limit": 25,
                "time_window": {"earliest": "earliest=-24h", "latest": "latest=now"},
            }
        },
        "consumption_rules": [
            "Route-plan parameters win on conflict.",
            "Rendered SPL must pass Q1A validator; no relaxed retries.",
            "Reasoning models rejected for this role.",
        ],
    },
    "template_match_semantic_assist": {
        "model_family": "Foundation-sec-8B-Instruct only",
        "purpose": "Emit semantic hints for template matching; deterministic matcher is authoritative.",
        "max_input_tokens": "2000",
        "system_instruction": (
            "Return JSON only. Advisory semantic hints for template matching. "
            "Never pick template_id, never emit SPL, never authorize execution, "
            "and never use confidence as authority. Fill blanks only; deterministic matcher, "
            "Environment KB/source-profile, and catalogue/manual bindings win on every disagreement."
        ),
        "authority_hierarchy": AUTHORITY_HIERARCHY_RULES,
        "review_only_safety": REVIEW_ONLY_SAFETY_RULES,
        "include": ["user_query", "normalized_route_plan", "approved_datamodels", "cim_field_allowlists"],
        "output_schema": {
            "llm_semantic_hints": {
                "source_class_hint": "okta_authentication_logs",
                "datamodel_hint": "Authentication",
                "field_aliases": {"failed login user": "user"},
            }
        },
        "consumption_rules": [
            "Hints are recorded in route_plan_shadow only when shadow mode is enabled.",
            "Deterministic template_matcher wins on every disagreement.",
            "Reasoning models are rejected for this role.",
            "Adapter strips template_id and SPL fragments.",
        ],
    },
    "analyst_summary_narration": {
        "model_family": "Foundation-sec-8B-Instruct only",
        "purpose": "Narrate a short shadow summary from structured route-plan lineage input only.",
        "max_input_tokens": "3000",
        "system_instruction": (
            "Return JSON only. At most two summary sentences and exactly three technical_trace_bullets. "
            "Use only facts present in structured_input. Never claim execution, production runs, or readiness to run. "
            "Never recommend actions."
        ),
        "include": ["structured_input"],
        "output_schema": {
            "summary_sentence_1": "Shadow route-plan metadata was recorded without execution.",
            "summary_sentence_2": None,
            "technical_trace_bullets": [
                "Preflight and route-plan shadow statuses are advisory only.",
                "Template match shadow uses deterministic matcher output.",
                "Rendered SPL hash may be present; SPL text is never returned here.",
            ],
        },
        "consumption_rules": [
            "Shadow-only inside investigation lineage reveal; analyst answer envelope unchanged.",
            "Reasoning models rejected for this role.",
            "Forbidden phrases and unsupported claims drop narration; deterministic skeleton wins.",
        ],
    },
    "route_plan_candidate_generator": {
        "model_family": "Foundation-sec-8B-Instruct only",
        "purpose": "Emit a route-plan candidate JSON for shadow observation; deterministic routing wins.",
        "max_input_tokens": "4000",
        "system_instruction": (
            "Return JSON only. Propose primary_skill, operation_type, source_class, and evidence_needs. "
            "Never emit SPL, MCP tools, lookup_name, or detection_ref. Use detection_family only when needed. "
            "Never authorize execution or use confidence as authority. Fill blanks only; deterministic routing, "
            "Environment KB/source-profile, and catalogue/manual bindings win on every disagreement."
        ),
        "authority_hierarchy": AUTHORITY_HIERARCHY_RULES,
        "review_only_safety": REVIEW_ONLY_SAFETY_RULES,
        "few_shot_coverage": SOC_FEW_SHOT_COVERAGE,
        "include": ["user_query", "preflight_status", "missing_slots", "runtime_skill_catalog"],
        "output_schema": {
            "primary_skill": "aggregate_and_rank",
            "operation_type": "top_n",
            "source_class": "okta_authentication_logs",
            "evidence_needs": {
                "datamodel": "Authentication",
                "group_by": ["user"],
                "metric": {"type": "count", "field": "failed_login_count"},
            },
            "time_window": None,
            "limit": 10,
            "clarification_questions": [],
            "rationale": "Shadow candidate only.",
        },
        "consumption_rules": [
            "Shadow-only: deterministic preflight, validator, and template match own authority.",
            "Reasoning models are rejected for this role.",
            "Wrapper-tolerant JSON extraction; no repair or silent field injection.",
            "Adapter strips detection_ref and SPL fragments.",
        ],
    },
}

for _reasoning_role in ("mitre_reasoner", "missing_evidence_reasoner", "risk_rationale_reasoner"):
    PROMPT_CONTRACTS[_reasoning_role] = {
        **PROMPT_CONTRACTS["pattern_reasoner"],
        "purpose": f"Produce advisory {_reasoning_role.replace('_', ' ')} output from already provided evidence.",
    }

# The rationale roles receive a fixed decision dump and, without a worked example,
# the 8B model echoes the dump back verbatim instead of explaining it (measured
# 2026-06-16). A role-matched 1-shot anti-echo instruction makes it emit real
# reasoning prose in the keys ``_prose_from_payload`` actually reads.
PROMPT_CONTRACTS["mitre_reasoner"] = {
    **PROMPT_CONTRACTS["mitre_reasoner"],
    "system_instruction": (
        PROMPT_CONTRACTS["mitre_reasoner"]["system_instruction"]
        + " Do NOT repeat or echo the decision dump back. Write NEW explanatory prose. "
        "Use these keys: reasoning_summary (string), mitre_reasoning (array of "
        '{"technique_id","status","reasoning"}). No markdown fences.\n'
        "EXAMPLE (different dump — P3, candidate T1071, evidence-supported none):\n"
        '{"reasoning_summary":"The activity matches command-and-control patterns but no '
        'executed evidence confirms it, so it stays candidate-only at P3.",'
        '"mitre_reasoning":[{"technique_id":"T1071","status":"candidate","reasoning":'
        '"Periodic outbound beacons suggest C2 but were not validated against threat intel"}]}'
    ),
}
PROMPT_CONTRACTS["risk_rationale_reasoner"] = {
    **PROMPT_CONTRACTS["risk_rationale_reasoner"],
    "system_instruction": (
        PROMPT_CONTRACTS["risk_rationale_reasoner"]["system_instruction"]
        + " Do NOT repeat or echo the decision dump back. Write NEW explanatory prose. "
        "Use these keys: why_selected (array of strings), why_not_higher (array of strings), "
        "escalate_if (array of strings). No markdown fences.\n"
        "EXAMPLE (different dump — P2, brute force then success, no privileged account):\n"
        '{"why_selected":["Repeated failed logins followed by a success indicates a likely '
        'account takeover attempt"],"why_not_higher":["No privileged or service account '
        'confirmed on the targeted identity"],"escalate_if":["Post-login privileged actions '
        'or lateral movement are observed"]}'
    ),
}

PROMPT_CONTRACTS["mitre_candidate_mapper"] = {
    "model_family": "Foundation-sec-8B-Instruct",
    "purpose": "Suggest MITRE ATT&CK candidate technique IDs for a SOC question; advisory only; IDs validated against local bundle.",
    "max_input_tokens": "2000",
    "system_instruction": (
        "You are a MITRE ATT&CK candidate mapping assistant for a SOC. "
        "Return JSON only. Do not add markdown or prose before or after JSON. "
        "Do not invent ATT&CK IDs. Use only IDs from MITRE ATT&CK Enterprise. "
        "If the question is too generic for ATT&CK, return empty arrays and explain in not_applicable_reason. "
        "Output is advisory only. SOC approval is required before any technique becomes authoritative. "
        "Do not include mitigations, detection SPL, or recommended actions. "
        "Each technique MUST be an object with EXACTLY these keys: "
        '"technique_id" (bare ATT&CK ID such as "T1110" or "T1110.001" with no name appended), '
        '"technique_name", "confidence" (one of high/medium/low), and "reason" (short). '
        "Never return technique strings like \"T1110 - Brute Force\". List the most likely "
        "technique first in primary_techniques.\n"
        "EXAMPLE for a different question (\"PowerShell spawned by Word with an encoded command\"):\n"
        '{"primary_techniques":[{"technique_id":"T1059.001","technique_name":"PowerShell",'
        '"confidence":"high","reason":"Encoded PowerShell command executed"}],'
        '"secondary_techniques":[{"technique_id":"T1566.001","technique_name":"Spearphishing Attachment",'
        '"confidence":"medium","reason":"Office parent process suggests a malicious document"}],'
        '"not_applicable_reason":null,'
        '"assumptions":["Word spawning PowerShell is not an approved admin workflow"]}'
    ),
    "include": ["soc_question", "question_ref", "use_case_id", "local_technique_hints"],
    "exclude": [
        "Splunk rows",
        "RAG chunks",
        "full developer trace",
        "credentials",
        "SPL",
        "detection logic",
    ],
    "output_schema": {
        "primary_techniques": [
            {
                "technique_id": "T1110",
                "technique_name": "Brute Force",
                "confidence": "high",
                "reason": "short reason",
            }
        ],
        "secondary_techniques": [
            {
                "technique_id": "T1110.001",
                "technique_name": "Password Guessing",
                "confidence": "medium",
                "reason": "short reason",
            }
        ],
        "not_applicable_reason": None,
        "assumptions": ["short assumption strings"],
    },
    "consumption_rules": [
        "Extract first balanced JSON object; attempt one schema repair if needed.",
        "Validate all technique_id values against local ATT&CK bundle before use.",
        "IDs not in local bundle → downgrade to needs_review or not_mapped.",
        "Weak rationale or broad/generic mapping → downgrade to needs_review.",
        "LLM output alone cannot set status=supported or populate mitre_permitted[].",
        "Output is review-queue and trace only; SOC approval required to promote.",
        "Parse failure after repair → record parse_failed; keep deterministic status.",
    ],
}

PROMPT_CONTRACTS["guided_investigation_plan_proposer"] = {
    "model_family": "Foundation-sec-8B-Instruct",
    "purpose": "Propose bounded InvestigationPlan fields for guided hybrid hunts (advisory only).",
    "max_input_tokens": "2000-3000",
    "system_instruction": (
        "You are V.AI SOC guided investigation planner. Return JSON only. "
        "Propose hypotheses, evidence needs, and optional read-only discovery tool IDs. "
        "Never emit raw SPL, severity, execution flags, route changes, remediation, or invented indexes."
        f"{_AUTHORITY_PROMPT}"
        f"{_REVIEW_ONLY_PROMPT}"
    ),
    "output_schema": {
        "objectives": [],
        "hypotheses": [],
        "evidence_needed": [],
        "data_categories": [],
        "rag_sufficient": False,
        "env_kb_needed": False,
        "discovery_needed": False,
        "read_only_tools": [],
        "safe_spl_templates": [],
        "spl_review_requested": False,
        "clarification_needed": False,
        "clarification_questions": [],
        "refinement_recommended": False,
        "rationale": "",
    },
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
