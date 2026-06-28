from __future__ import annotations

import json
import subprocess
import sys

from app.config import Settings
from app.llm.prompts import (
    AUTHORITY_HIERARCHY_RULES,
    PROMPT_CONTRACTS,
    REVIEW_ONLY_SAFETY_RULES,
    SOC_FEW_SHOT_COVERAGE,
)
from app.llm.registry_settings import ROLE_DEFAULTS, build_llm_governance_status
from app.llm.sidecar_clients import build_intent_advisory_prompt


def test_prompt_contracts_cover_registry_roles() -> None:
    role_ids = {item["role"] for item in ROLE_DEFAULTS}

    assert role_ids.issubset(set(PROMPT_CONTRACTS))


def test_intent_shadow_classifier_prompt_contract_requires_clarification_for_deictic_alerts() -> None:
    contract = PROMPT_CONTRACTS["intent_shadow_classifier"]
    instruction = contract["system_instruction"]
    consumption = " ".join(contract["consumption_rules"])

    assert "Return JSON only" in instruction
    assert "Do not add markdown or prose" in instruction
    assert "Use allowed enums only" in instruction
    assert "Do not invent use_case_id" in instruction
    assert "Do not invent entities" in instruction
    assert "`this alert`" in instruction
    assert "requested_output_type must be clarification" in instruction
    assert "Deterministic clarification guard remains authoritative" in instruction
    assert "Authority hierarchy" in instruction
    assert "Review-only safety" in instruction
    assert contract["authority_hierarchy"] == AUTHORITY_HIERARCHY_RULES
    assert contract["review_only_safety"] == REVIEW_ONLY_SAFETY_RULES
    assert contract["few_shot_coverage"] == SOC_FEW_SHOT_COVERAGE
    assert "Confidence is advisory metadata only" in consumption


def test_reasoning_advisory_prompt_contract_is_advisory_only() -> None:
    for role in ("pattern_reasoner", "mitre_reasoner", "missing_evidence_reasoner", "risk_rationale_reasoner"):
        contract = PROMPT_CONTRACTS[role]
        instruction = contract["system_instruction"]
        schema = contract["output_schema"]

        assert "Return JSON only" in instruction
        assert "adapter may extract JSON" in instruction
        assert "advisory only" in instruction
        assert "Cannot override severity" in instruction
        assert "Cannot override MITRE status" in instruction
        assert "Cannot override SOP citation" in instruction
        assert "Cannot add remediation" in instruction
        assert "Cannot decide execution eligibility" in instruction
        assert "why_selected" in schema
        assert "why_not_higher" in schema
        assert "escalate_if" in schema


def test_analyst_response_prompt_contract_has_authority_and_evidence_limits() -> None:
    contract = PROMPT_CONTRACTS["analyst_response_drafter"]
    instruction = contract["system_instruction"]
    consumption = " ".join(contract["consumption_rules"])

    assert "Return JSON only" in instruction
    assert "Severity is fixed by the severity matrix" in instruction
    assert "MITRE mapping/status is fixed by MITRE policy" in instruction
    assert "SOP citation/source refs are fixed by governed RAG" in instruction
    assert "Allowed/blocked actions are fixed by action policy" in instruction
    assert "Priority enum must be P1/P2/P3/P4 only" in instruction
    assert "Do not compute aggregate counts" in instruction
    assert "use only precomputed aggregate values supplied by StructuredContext" in instruction
    assert "SOP guidance must be copied from provided SOP guidance text" in instruction
    assert "Do not claim unknown facts positively or negatively" in instruction
    assert "privileged-account status" in instruction
    assert "Semantic guard rules validate evidence presence" in consumption


def test_spl_advisory_prompt_contract_is_candidate_only() -> None:
    contract = PROMPT_CONTRACTS["spl_advisory_generator"]
    instruction = contract["system_instruction"]
    consumption = " ".join(contract["consumption_rules"])

    assert "Candidate-only" in instruction
    assert "Never execution eligible" in instruction
    assert "`execution_eligible` is ignored by the adapter and forced false" in instruction
    assert "template-first" in instruction
    assert "Do not include alert, sendemail, write" in instruction
    assert "Do not invent index, sourcetype, or fields" in instruction
    assert "Use SCD field map only" in instruction
    assert "Raw candidate_spl never reaches MCP" in instruction
    assert "Environment KB/source-profile values win" in instruction
    assert "Do not claim live results" in instruction
    assert contract["output_schema"]["execution_eligible"] is False
    assert "Adapter forces execution_eligible=false" in consumption


def test_llm_prompt_contracts_include_authority_and_review_only_rules_for_advisory_roles() -> None:
    for role in (
        "template_render_parameter_assist",
        "template_match_semantic_assist",
        "route_plan_candidate_generator",
    ):
        contract = PROMPT_CONTRACTS[role]
        instruction = contract["system_instruction"]

        assert contract["authority_hierarchy"] == AUTHORITY_HIERARCHY_RULES
        assert contract["review_only_safety"] == REVIEW_ONLY_SAFETY_RULES
        assert "Fill blanks only" in instruction
        assert "Environment KB/source-profile" in instruction
        assert "SPL" in instruction or "execution" in instruction


def test_runtime_intent_advisory_prompt_carries_authority_safety_and_few_shots() -> None:
    prompt = build_intent_advisory_prompt(
        query="Check Cisco ASA hits to known bad IPs",
        context_block="Context: deterministic source profile is firewall_logs.",
    )

    assert "Authority hierarchy:" in prompt
    assert "User-explicit values win" in prompt
    assert "Environment KB/source-profile values win" in prompt
    assert "LLM output fills blanks only" in prompt
    assert "Review-only safety:" in prompt
    assert "never authorize execution" in prompt
    assert "Do not claim live results" in prompt
    assert "Cisco ASA IOC lookup" in prompt
    assert "SCADA threshold anomaly" in prompt
    assert "SMB top talkers" in prompt
    assert "Off-shift logon" in prompt
    assert "Unsafe containment" in prompt
    assert "Return ONE JSON object" in prompt


def test_role_suitability_matches_foundation_sec_observed_behavior() -> None:
    block = build_llm_governance_status()
    suitability = {item["provider_id"]: item["checks"] for item in block["role_suitability"]}

    instruct = suitability["foundation_sec_instruct"]
    assert instruct["intent_shadow_classifier"] == "suitable_with_guard"
    assert instruct["analyst_response_drafter"] == "suitable_with_guard"
    assert instruct["investigation_note_drafter"] == "suitable_with_guard"
    assert instruct["spl_advisory_generator"] == "candidate_only"
    assert instruct["spl_advisory_recommendation"] == "not_recommended"
    assert instruct["final_answer_without_guard"] == "not_allowed"

    reasoning = suitability["foundation_sec_reasoning"]
    assert reasoning["pattern_reasoner"] == "suitable_with_guard"
    assert reasoning["mitre_reasoner"] == "suitable_with_guard"
    assert reasoning["missing_evidence_reasoner"] == "suitable_with_guard"
    assert reasoning["risk_rationale_reasoner"] == "suitable_with_guard"
    assert reasoning["analyst_response_drafter"] == "optional_not_primary"
    assert reasoning["spl_advisory_generator"] == "candidate_only"
    assert reasoning["spl_advisory_recommendation"] == "not_recommended"
    assert reasoning["final_answer_without_guard"] == "not_allowed"


def test_governance_status_includes_advisory_deterministic_authority_wording() -> None:
    block = build_llm_governance_status()
    serialized = json.dumps(block)

    assert block["authority_note"] == "Foundation-sec outputs are advisory until validated by deterministic policy and Answer Guard."
    assert "Foundation-sec outputs are advisory until validated by deterministic policy and Answer Guard." in serialized
    assert "severity_label" in block["deterministic_authorities"]
    assert "mitre_mapping_status" in block["deterministic_authorities"]
    assert "sop_citation_source_refs" in block["deterministic_authorities"]
    assert "mcp_execution_eligibility" in block["deterministic_authorities"]


def test_final_synthesis_answer_guard_and_live_calls_remain_disabled() -> None:
    fresh = Settings(_env_file=None)
    block = build_llm_governance_status()

    assert fresh.ai_soc_llm_final_synthesis_enabled is False
    assert fresh.ai_soc_llm_answer_guard_enabled is False
    assert block["final_synthesis_enabled"] is False
    assert block["answer_guard_enabled"] is False
    assert "No real LLM is called in this stage." in " ".join(block["notes"])


def test_stage_3ji3_does_not_import_dormant_semantic_guards() -> None:
    code = (
        "import sys;"
        "sys.modules.pop('app.answer_guard.rules', None);"
        "import app.llm.prompts;"
        "from app.llm.registry_settings import build_llm_governance_status;"
        "build_llm_governance_status();"
        "import app.api.routes_settings;"
        "import app.api.routes_chat;"
        "raise SystemExit(1 if 'app.answer_guard.rules' in sys.modules else 0)"
    )
    completed = subprocess.run([sys.executable, "-c", code], check=False)

    assert completed.returncode == 0
