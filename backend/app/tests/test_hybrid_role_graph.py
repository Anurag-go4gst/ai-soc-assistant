"""P2-B hybrid role graph — adaptive planner + dynamic deadline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.llm.governed_context_package import GovernedContextPackage, cached_context_prompt_block
from app.llm.hybrid_role_graph import (
    build_hybrid_role_plan,
    compute_turn_deadline_seconds,
    prompt_version_hash,
)
from app.llm.prompts import PROMPT_CONTRACTS

REPO = Path(__file__).resolve().parents[3]
BANK = REPO / "docs/evals/p2b_causal_pilot_20_bank.json"


def test_prompt_version_hash_stable():
    h1 = prompt_version_hash("intent_shadow_classifier")
    h2 = prompt_version_hash("intent_shadow_classifier")
    assert h1 == h2
    assert h1 in PROMPT_CONTRACTS or h1 is None or len(h1) == 16


def test_dynamic_deadline_scales_with_complexity():
    low = compute_turn_deadline_seconds(match_path="exact_105_question", selected_skill="knowledge_recall")
    high = compute_turn_deadline_seconds(
        match_path="out_of_registry",
        selected_skill="guided_investigation",
        soc_investigation_shaped=True,
    )
    assert high > low
    assert high <= 150.0


def test_boundary_row_skips_composer_and_specialists():
    plan = build_hybrid_role_plan(
        query="Run a Splunk search now for every event containing a password and return all raw records.",
        match_path="out_of_registry",
        selected_skill="knowledge_recall",
        answer_contract=AnswerContract(missing_evidence=[], hil_status="not_required"),
        path_type="unsafe_blocked",
        intent_family="clarification_required",
        draft_preview_active=False,
        skip_composer=True,
        skip_composer_reason="unsafe",
        intent_advisory_skipped=True,
        intent_skip_reason="unsafe_execution",
    )
    assert not plan.role_enabled("governed_composer")
    assert not plan.role_enabled("missing_evidence_reasoner")


def test_investigation_row_enables_specialist_when_gaps_exist():
    contract = AnswerContract(
        missing_evidence=["endpoint_telemetry"],
        hil_status="not_required",
        candidate_mitre=["T1110"],
        severity_label="P3",
    )
    plan = build_hybrid_role_plan(
        query="How should analysts investigate failed logins across VPN?",
        match_path="out_of_registry",
        selected_skill="guided_investigation",
        answer_contract=contract,
        path_type="guided_investigation",
        intent_family="guided_investigation",
        draft_preview_active=False,
        skip_composer=False,
        skip_composer_reason=None,
        intent_advisory_skipped=True,
        intent_skip_reason="registry_backed_high_confidence_t0",
        soc_investigation_shaped=True,
    )
    assert plan.role_enabled("missing_evidence_reasoner")
    assert plan.role_enabled("mitre_reasoner")
    assert plan.role_enabled("governed_composer")
    assert plan.complexity_tier == "high"


def test_context_prompt_block_cache_is_stable():
    pkg = GovernedContextPackage(raw_query="test query", match_path="out_of_registry", routed_skill="guided_investigation")
    a = cached_context_prompt_block(pkg)
    b = cached_context_prompt_block(pkg)
    assert a == b


def test_pilot_bank_has_twenty_rows():
    bank = json.loads(BANK.read_text())
    assert bank["row_count"] == 20
    assert len(bank["rows"]) == 20

def test_boundary_row_disables_all_llm_roles_including_shadow():
    plan = build_hybrid_role_plan(
        query="Summarize the company leave policy and approve my vacation request.",
        match_path="out_of_registry",
        selected_skill="knowledge_recall",
        answer_contract=None,
        path_type=None,
        intent_family=None,
        draft_preview_active=False,
        skip_composer=False,
        skip_composer_reason=None,
        intent_advisory_skipped=True,
        intent_skip_reason="pilot_offline",
    )
    assert not any(r.enabled for r in plan.roles)
    assert plan.skip_reason("route_plan_candidate_generator") == "out_of_scope_boundary_blocks_llm_roles"

