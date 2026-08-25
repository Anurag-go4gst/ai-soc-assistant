"""Unseen T4 qualification pack — emit-prompts only, no live Cisco."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from app.chat.semantic_t4_understanding import (
    _SEMANTIC_T4_SYSTEM_PROMPT,
    _build_semantic_t4_user_prompt,
)

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "eval_t4_unseen_qualification.py"
_spec = importlib.util.spec_from_file_location("eval_t4_unseen_qualification", _SCRIPT)
assert _spec and _spec.loader
harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness)

_REQUIRED_IDS = [
    "unresolved_referent",
    "explicit_host",
    "explicit_time_range",
    "followup_from_context",
    "vague_actionable_hunt",
    "knowledge_only",
    "competing_explanations",
    "semantic_strength_trap",
    "material_dual_meaning",
]


def test_nine_unseen_classes() -> None:
    assert len(harness.CASES) == 9
    assert [case["case_id"] for case in harness.CASES] == _REQUIRED_IDS
    queries = " ".join(case["query"].lower() for case in harness.CASES)
    assert "dga" not in queries
    assert "algorithmically generated" not in queries
    assert "powershell" not in queries


def test_emit_prompts_does_not_call_the_model(monkeypatch) -> None:
    calls: list[str] = []

    def _forbidden(query: str, _contract: object) -> str:
        calls.append(query)
        raise AssertionError("emit-prompts must not call the live T4 provider")

    monkeypatch.setattr(
        "app.chat.semantic_t4_understanding._live_single_hop_provider",
        _forbidden,
    )
    report = harness.build_report(mode="emit-prompts")
    assert calls == []
    assert report["mode"] == "emit-prompts"
    assert report["invariants"]["no_live_cisco"] is True
    assert harness.assert_output_contract(report) == []


def test_each_record_has_locked_prompt_and_expected_behaviour() -> None:
    report = harness.build_report(mode="emit-prompts")
    assert len(report["cases"]) == 9
    for row, case in zip(report["cases"], harness.CASES, strict=True):
        for field in harness.CASE_RECORD_FIELDS:
            assert field in row, field
        prompt = row["exact_t4_prompt"]
        assert prompt["system"] == _SEMANTIC_T4_SYSTEM_PROMPT
        pack = harness._prompt_pack(case)
        expected_user = _build_semantic_t4_user_prompt(case["query"], pack["_base_contract"])
        assert prompt["user"] == expected_user
        assert row["raw_proposal"] is None
        assert isinstance(row["clarification_expected"], bool)
        assert row["forbidden_strengthening"]
        assert row["expected_authority_behaviour"]
        assert "Do not grant route, capability, SPL, MCP, RBAC, HIL" in prompt["system"]
        assert "competing_hypotheses" in prompt["system"]
        # P2-B: the patch-only framing is gone; explicit literals are binding instead.
        assert "Never contradict EXPLICIT_USER_LITERAL_CONSTRAINTS" in prompt["system"]


def test_referent_stays_production_clarify_hunts_permit_t4() -> None:
    report = harness.build_report(mode="emit-prompts")
    by_id = {row["case_id"]: row for row in report["cases"]}
    referent = by_id["unresolved_referent"]
    assert referent["clarification_expected"] is True
    assert referent["t4_call_permitted"] is True
    assert referent["qualification_authority"] == "t4_semantic"
    assert referent["production_next_action"] == "CALL_T4"
    dual = by_id["material_dual_meaning"]
    assert dual["clarification_expected"] is True
    assert dual["t4_call_permitted"] is True
    hunts = [
        "explicit_host",
        "explicit_time_range",
        "followup_from_context",
        "vague_actionable_hunt",
        "competing_explanations",
        "semantic_strength_trap",
    ]
    for case_id in hunts:
        assert by_id[case_id]["clarification_expected"] is False, case_id
        assert by_id[case_id]["t4_call_permitted"] is True, case_id
        assert by_id[case_id]["qualification_authority"] == "t4_semantic", case_id
    assert by_id["knowledge_only"]["clarification_expected"] is False
    assert by_id["followup_from_context"]["supplied_conversation_context"]["host"] == "ws-finance-04"


def test_injected_good_proposals_meet_pass_gate() -> None:
    report = harness.build_report(mode="emit-prompts")
    scores = report["injected_contract_scores"]
    assert len(scores) == 9
    assert all(row["schema_valid"] for row in scores)
    assert all(row["no_invented_observed_facts"] for row in scores)
    assert all(row["no_authority_widening"] for row in scores)
    assert all(row["clarification_correct"] for row in scores)
    assert all(row["semantic_strength_preserved"] for row in scores)
    semantic_pass = sum(1 for row in scores if row["semantic_goal_acceptable"])
    assert semantic_pass >= 8


def test_injected_clarification_on_hunt_is_rejected() -> None:
    case = next(item for item in harness.CASES if item["case_id"] == "vague_actionable_hunt")
    pack = harness._prompt_pack(case)
    from app.config import settings

    previous = settings.ai_soc_t4_semantic_understanding_enabled
    settings.ai_soc_t4_semantic_understanding_enabled = True
    try:
        from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic
        import json

        enriched = maybe_enrich_t4_semantic(
            pack["_base_contract"],
            query=case["query"],
            raw_output_provider=lambda _q, _c: json.dumps(
                {
                    "normalized_goal": "find credential stuffing",
                    "clarification_required": True,
                    "clarification_reason": "need a threshold and example logs",
                    "semantic_ambiguity": "unambiguous",
                }
            ),
        )
    finally:
        settings.ai_soc_t4_semantic_understanding_enabled = previous
    assert enriched.clarification_required is False
    reasons = (enriched.provenance.get("semantic_t4") or {}).get("rejected_reasons") or []
    assert "clarification_without_unresolved_referent" in reasons


def test_live_flag_is_refused() -> None:
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "must not call Cisco" in text
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"system", "popen"}
